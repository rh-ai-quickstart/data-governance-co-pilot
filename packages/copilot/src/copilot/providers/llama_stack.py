"""
Llama Stack Provider Implementation.

This provider delegates agentic orchestration to Llama Stack's Agents API.
Llama Stack manages the complete agentic loop - this provider just streams events.
"""

import logging
import time
from typing import Any, AsyncGenerator

from llama_stack_client import LlamaStackClient

from .base import LLMProvider

logger = logging.getLogger(__name__)


class LlamaStackProvider(LLMProvider):
    """
    Llama Stack provider: Delegates to Llama Stack for agentic orchestration.

    Features:
    - Toolgroup registration with Llama Stack
    - Agent creation with MCP tools
    - Event streaming from Agents API
    - Event mapping to standardized schema
    - Simplified architecture (Llama Stack manages agentic loop)
    """

    def __init__(self, config: dict[str, Any], governance_policy: str | None = None):
        """
        Initialize Llama Stack provider.

        Args:
            config: Configuration dict with keys:
                - llama_stack_base_url: Llama Stack endpoint URL
                - llama_stack_model: Model identifier (vllm-inference/<name> format)
                - llm_temperature: Sampling temperature (0.0-2.0)
                - llm_min_p: Min-P sampling threshold (0.0-1.0)
                - mcp_server_url: MCP server endpoint for toolgroup registration
            governance_policy: Optional governance policy text to include in agent instructions
        """
        self.config = config
        self.governance_policy = governance_policy

        # Llama Stack Configuration
        self.llama_stack_base_url = config.get("llama_stack_base_url", "http://copilot-llama-stack:8000")
        self.llama_stack_model = config.get("llama_stack_model", "vllm-inference/redhataillama-31-8b-instruct")
        self.mcp_server_url = config.get("mcp_server_url", "http://pg-airman-mcp-service:8000")

        # Sampling Parameters
        self.temperature = float(config.get("llm_temperature", 0.1))
        self.min_p = float(config.get("llm_min_p", 0.1))

        # Llama Stack client and agent state
        self.client = None
        self.agent_id = None
        self.toolgroup_id = "mcp::pg_airman"
        self._initialized = False
        self._tool_count = 0

        # Session management: map conversation_id -> session_id
        self._session_store = {}

        logger.info(f"Llama Stack provider initialized")
        logger.info(f"  Base URL: {self.llama_stack_base_url}")
        logger.info(f"  Model: {self.llama_stack_model}")
        logger.info(f"  MCP Server: {self.mcp_server_url}")

    async def initialize(self) -> None:
        """
        Initialize Llama Stack connection and create agent.

        Steps:
        1. Connect to Llama Stack
        2. Register MCP toolgroup
        3. Create agent with toolgroups configuration
        """
        try:
            logger.info("Initializing Llama Stack provider...")

            # Create Llama Stack client
            self.client = LlamaStackClient(base_url=self.llama_stack_base_url)
            logger.info(f"Connected to Llama Stack at {self.llama_stack_base_url}")

            # Get MCP tool runtime provider
            providers = self.client.providers.list()
            tool_provider = next(
                (p for p in providers if p.api == "tool_runtime"),
                None
            )

            if not tool_provider:
                raise RuntimeError("No tool_runtime provider found in Llama Stack")

            logger.info(f"Found tool runtime provider: {tool_provider.provider_id}")

            # Extract MCP endpoint URI from tool provider config
            mcp_endpoint_uri = tool_provider.config.get("mcp_endpoint", {}).get("uri")
            if not mcp_endpoint_uri:
                # Fall back to our configured MCP server URL
                mcp_endpoint_uri = f"{self.mcp_server_url}/sse"
                logger.info(f"Using configured MCP endpoint: {mcp_endpoint_uri}")

            # Register MCP toolgroup
            logger.info(f"Registering toolgroup '{self.toolgroup_id}'...")
            self.client.toolgroups.register(
                toolgroup_id=self.toolgroup_id,
                provider_id=tool_provider.provider_id,
                mcp_endpoint={"uri": mcp_endpoint_uri}
            )
            logger.info(f"Toolgroup '{self.toolgroup_id}' registered successfully")

            # Get tool count from toolgroup
            try:
                tools = self.client.toolgroups.get(toolgroup_id=self.toolgroup_id)
                if tools and hasattr(tools, 'tools'):
                    self._tool_count = len(tools.tools)
                    logger.info(f"Toolgroup has {self._tool_count} tools")
            except Exception as e:
                logger.warning(f"Could not get tool count from toolgroup: {e}")
                self._tool_count = 0

            # Create agent with toolgroups
            logger.info("Creating agent...")
            agent = self.client.alpha.agents.create(
                agent_config={
                    "model": self.llama_stack_model,
                    "instructions": self.get_system_prompt(enable_reasoning=True),
                    "toolgroups": [self.toolgroup_id],
                    "tool_choice": "auto",
                    # Llama Stack passes sampling_params directly to underlying inference engine (vLLM)
                    # Unlike OpenAI client (used in MCP-Direct), we can pass vLLM-specific params like min_p directly
                    "sampling_params": {
                        "max_tokens": 2048,
                        "temperature": self.temperature,
                        "min_p": self.min_p,
                    },
                }
            )
            self.agent_id = agent.agent_id
            logger.info(f"Agent created with ID: {self.agent_id}")

            self._initialized = True
            logger.info("Llama Stack provider initialization complete!")

        except Exception as e:
            logger.error(f"Failed to initialize Llama Stack provider: {e}", exc_info=True)
            raise

    async def process_query_stream(
        self,
        user_query: str,
        conversation_id: str | None,
        enable_reasoning: bool,
        messages: list[dict] | None = None
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Process query via Llama Stack Agents API.

        Steps:
        1. Create or reuse session
        2. Execute turn with streaming
        3. Map Llama Stack events to our schema
        4. Yield standardized events

        Args:
            user_query: User's question
            conversation_id: Optional conversation ID for session management
            enable_reasoning: Whether to show thinking (affects instructions)
            messages: Optional message history (Llama Stack manages this in sessions)
        """
        if not self._initialized or not self.client or not self.agent_id:
            logger.error("Llama Stack provider not initialized")
            yield {
                "type": "error",
                "message": "Llama Stack provider not initialized. Please check logs."
            }
            return

        start_time = time.time()
        session_id = None
        final_content = ""
        tool_calls_made = 0
        iteration_count = 0
        accumulated_messages = messages.copy() if messages else []

        # Track timing for summary (like MCP-Direct)
        total_llm_time = 0.0
        total_mcp_time = 0.0
        step_start_time = None

        try:
            # Emit query start event (like MCP-Direct)
            yield {
                "type": "query_start",
                "query": user_query,
                "timestamp": time.strftime('%H:%M:%S')
            }

            # Get or create session for this conversation
            if conversation_id and conversation_id in self._session_store:
                # Reuse existing session from memory
                session_id = self._session_store[conversation_id]
                logger.info(f"Reusing cached session for conversation {conversation_id}: {session_id}")
            else:
                # Check if session exists in Llama Stack (handles pod restarts)
                session_id = None
                session_name = f"session-{conversation_id}" if conversation_id else f"session-{int(time.time())}"

                if conversation_id:
                    try:
                        # List existing sessions for this agent
                        logger.info(f"Checking for existing session with name: {session_name}")
                        sessions = self.client.alpha.agents.session.list(agent_id=self.agent_id)

                        # Find session matching this conversation's name
                        for session in sessions:
                            if hasattr(session, 'session_name') and session.session_name == session_name:
                                session_id = session.session_id
                                logger.info(f"Found existing session in Llama Stack: {session_id}")
                                # Rebuild session_store cache
                                self._session_store[conversation_id] = session_id
                                break
                    except Exception as e:
                        logger.warning(f"Failed to list existing sessions: {e}")

                # Create new session if not found
                if not session_id:
                    logger.info(f"Creating new Llama Stack session: {session_name}")
                    session = self.client.alpha.agents.session.create(
                        agent_id=self.agent_id,
                        session_name=session_name
                    )
                    session_id = session.session_id
                    logger.info(f"Session created: {session_id}")

                    # Store session ID for future turns
                    if conversation_id:
                        self._session_store[conversation_id] = session_id
                        logger.info(f"Stored session_id {session_id} for conversation {conversation_id}")

            # Execute turn with streaming
            logger.info("Executing turn with streaming...")
            stream = self.client.alpha.agents.turn.create(
                agent_id=self.agent_id,
                session_id=session_id,
                messages=[
                    {"role": "user", "content": user_query}
                ],
                stream=True
            )

            # Stream and map events
            for chunk in stream:
                # Debug: log raw chunk structure
                logger.info(f"Received chunk: {type(chunk).__name__}, attrs: {dir(chunk)}")
                if hasattr(chunk, 'event'):
                    logger.info(f"  event: {chunk.event}")

                # Map Llama Stack event to our schema
                mapped_events = self._map_event(chunk, enable_reasoning)

                if not mapped_events:
                    logger.info(f"  No mapped events for chunk")
                else:
                    logger.info(f"  Mapped {len(mapped_events)} event(s): {[e.get('type') for e in mapped_events]}")

                for event in mapped_events:
                    # Track metrics and add iteration field to events
                    if event.get("type") == "iteration_start":
                        iteration_count += 1
                        event["iteration"] = iteration_count
                        event["max_iterations"] = 100  # Match MCP-Direct's convention
                        # Start timing this iteration/step
                        step_start_time = time.time()
                    elif event.get("type") == "tool_call":
                        tool_calls_made += 1
                        event["iteration"] = iteration_count  # Associate with current iteration
                        # LLM finished generating tool call - add to llm_time
                        if step_start_time is not None:
                            llm_step_time = time.time() - step_start_time
                            total_llm_time += llm_step_time
                    elif event.get("type") == "tool_result":
                        event["iteration"] = iteration_count  # Associate with current iteration
                        # Add MCP time if available in event
                        if "mcp_time" in event:
                            total_mcp_time += event["mcp_time"]
                    elif event.get("type") == "llm_thinking":
                        event["iteration"] = iteration_count  # Associate with current iteration
                    elif event.get("type") == "llm_content_delta":
                        event["iteration"] = iteration_count  # Associate with current iteration
                    elif event.get("type") == "turn_complete_internal":
                        # Capture final content but don't yield this internal event
                        final_content = event.get("content", "")
                        # Final LLM generation time
                        if step_start_time is not None:
                            llm_step_time = time.time() - step_start_time
                            total_llm_time += llm_step_time
                        continue  # Don't yield turn_complete_internal

                    # Debug log what we're actually yielding
                    if event.get("type") == "llm_content_delta":
                        logger.info(f"  Yielding llm_content_delta: iteration={event.get('iteration')}, content={event.get('content')[:50] if event.get('content') else 'NONE'}...")

                    yield event

            # Stream loop completed
            logger.info(f"Stream loop completed. final_content length: {len(final_content)}")

            # Update message history with current turn
            # Llama Stack manages session history, but service.py needs messages for conversation_store
            accumulated_messages.append({"role": "user", "content": user_query})
            accumulated_messages.append({"role": "assistant", "content": final_content})
            logger.info(f"Message history now has {len(accumulated_messages)} messages")

            # Emit timing summary (match MCP-Direct structure)
            end_time = time.time()
            query_total_time = end_time - start_time
            backend_overhead = query_total_time - total_llm_time - total_mcp_time

            logger.info(f"Emitting timing_summary...")
            yield {
                "type": "timing_summary",
                "total_time": query_total_time,
                "llm_time": total_llm_time,
                "mcp_time": total_mcp_time,
                "backend_overhead": backend_overhead,
                "iterations": iteration_count,
                "tool_calls": tool_calls_made,
                # Context info not available from Llama Stack - set to None
                "context_tokens_used": None,
                "context_tokens_limit": None,
                "context_usage_pct": None
            }

            # Emit final response with messages
            logger.info(f"Emitting final_response with content length: {len(final_content)}")
            yield {
                "type": "final_response",
                "content": final_content,
                "tool_calls": tool_calls_made,
                "conversation_id": conversation_id,
                "messages": accumulated_messages
            }

        except Exception as e:
            logger.info(f"EXCEPTION CAUGHT: {type(e).__name__}: {str(e)}")
            logger.error(f"Error processing query: {e}", exc_info=True)
            yield {
                "type": "error",
                "message": f"Llama Stack error: {str(e)}"
            }

    def _map_event(self, chunk, enable_reasoning: bool) -> list[dict[str, Any]]:
        """
        Map Llama Stack events to our standardized schema.

        Event mapping:
        - step_start → iteration_start
        - step_progress → llm_thinking (if thinking detected) or llm_content_delta
        - step_complete → tool_call + tool_result
        - turn_complete → final_response

        Args:
            chunk: Llama Stack event chunk
            enable_reasoning: Whether to include thinking events

        Returns:
            List of mapped events (may be multiple events from one chunk)
        """
        if not hasattr(chunk, 'event') or chunk.event is None:
            return []

        if not hasattr(chunk.event, 'payload') or chunk.event.payload is None:
            return []

        payload = chunk.event.payload

        if not hasattr(payload, 'event_type'):
            return []

        event_type = payload.event_type

        # Map step_start to iteration_start (but only for inference steps, not tool_execution)
        if event_type == "step_start":
            step_type = payload.step_type if hasattr(payload, 'step_type') else "unknown"
            # Only create new iteration for inference steps, not tool_execution
            # Tool execution is part of the same iteration as the inference that triggered it
            if step_type != "tool_execution":
                return [{
                    "type": "iteration_start",
                    "step_type": step_type
                }]
            else:
                # Don't emit iteration_start for tool_execution steps
                return []

        # Map step_progress to content deltas
        elif event_type == "step_progress":
            events = []

            # Check for text delta (structure: payload.delta.text)
            if hasattr(payload, 'delta') and payload.delta:
                delta_type = payload.delta.type if hasattr(payload.delta, 'type') else None

                # Log tool_call deltas for debugging
                if delta_type == 'tool_call':
                    logger.info(f"  step_progress tool_call delta: {payload.delta}")
                    if hasattr(payload.delta, 'tool_call'):
                        tc_delta = payload.delta.tool_call
                        logger.info(f"    tool_call content: '{tc_delta}'")
                        logger.info(f"    parse_status: {payload.delta.parse_status if hasattr(payload.delta, 'parse_status') else 'N/A'}")

                # Handle text deltas only (skip tool_call deltas as they're internal)
                if delta_type == 'text' and hasattr(payload.delta, 'text'):
                    delta_text = payload.delta.text
                    if delta_text:
                        # Try to detect thinking content (heuristic: starts with reasoning keywords)
                        # This is a backup - Llama Stack models may not expose thinking separately
                        if enable_reasoning and any(keyword in delta_text.lower() for keyword in ["<think>", "reasoning:", "let me think"]):
                            events.append({
                                "type": "llm_thinking",
                                "content": delta_text
                            })
                        else:
                            events.append({
                                "type": "llm_content_delta",
                                "content": delta_text  # Match MCP-Direct's field name
                            })

            return events

        # Map step_complete to tool_call + tool_result
        elif event_type == "step_complete":
            events = []

            if not hasattr(payload, 'step_details'):
                return events

            details = payload.step_details

            # Check for InferenceStep - tool_calls in api_model_response
            if hasattr(details, 'api_model_response'):
                response = details.api_model_response
                if hasattr(response, 'tool_calls') and response.tool_calls:
                    for tc in response.tool_calls:
                        # Parse arguments from JSON string to dict
                        import json

                        tool_name = tc.tool_name if hasattr(tc, 'tool_name') else "unknown"
                        logger.info(f"Processing tool call: {tool_name}")
                        logger.info(f"  Raw ToolCall object: {tc}")

                        arguments = {}
                        if hasattr(tc, 'arguments'):
                            raw_args = tc.arguments
                            logger.info(f"  Raw arguments (type={type(raw_args).__name__}, len={len(raw_args) if isinstance(raw_args, str) else 'N/A'}): '{raw_args}'")
                            logger.info(f"  Arguments repr: {repr(raw_args)}")
                            logger.info(f"  Arguments bytes: {raw_args.encode() if isinstance(raw_args, str) else 'N/A'}")

                            if raw_args:
                                try:
                                    arguments = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                                    logger.info(f"  Parsed arguments successfully: {arguments}")
                                except json.JSONDecodeError as e:
                                    logger.error(f"  JSONDecodeError: {e}")
                                    logger.error(f"  Failed at position {e.pos}: '{raw_args[max(0,e.pos-10):e.pos+10] if isinstance(raw_args, str) else 'N/A'}'")
                                    arguments = {}
                            else:
                                logger.warning(f"  Empty arguments string for tool {tool_name}")

                        events.append({
                            "type": "tool_call",
                            "tool_name": tool_name,
                            "arguments": arguments
                        })

            # Check for ToolExecutionStep - tool_calls and tool_responses directly in details
            if hasattr(details, 'tool_responses') and details.tool_responses:
                # Calculate MCP execution time from step timing
                mcp_time = 0.0
                if hasattr(details, 'started_at') and hasattr(details, 'completed_at'):
                    if details.started_at and details.completed_at:
                        mcp_time = (details.completed_at - details.started_at).total_seconds()

                for tr in details.tool_responses:
                    # Extract text from content items
                    result_text = ""
                    if hasattr(tr, 'content') and tr.content:
                        # content is a list of content items
                        for item in tr.content:
                            if hasattr(item, 'text'):
                                result_text = item.text
                                break

                    events.append({
                        "type": "tool_result",
                        "tool_name": tr.tool_name if hasattr(tr, 'tool_name') else "unknown",
                        "result": result_text,
                        "mcp_time": mcp_time  # Include timing info like MCP-Direct
                    })

            return events

        # Map turn_complete to final_response (this is just for logging, actual final sent separately)
        elif event_type == "turn_complete":
            if hasattr(payload.turn, 'output_message') and payload.turn.output_message:
                content = payload.turn.output_message.content
                return [{
                    "type": "turn_complete_internal",  # Internal marker, not sent to UI
                    "content": content
                }]

        return []

    def get_system_prompt(self, enable_reasoning: bool) -> str:
        """
        Build agent instructions for Llama Stack.

        Similar to MCP-Direct but optimized for Llama Stack's agent format.
        Note: Llama Stack uses standard OpenAI function calling, so no custom tags.

        Args:
            enable_reasoning: Whether to encourage reasoning in responses

        Returns:
            Agent instructions string
        """
        base_content = (
            "ROLE:\n"
            "You are a PostgreSQL Database Governance Co-Pilot with access to database analysis tools.\n\n"
            "CAPABILITIES:\n"
            "- Analyzing database schemas, tables, views, and relationships\n"
            "- Executing SQL queries and explaining results\n"
            "- Providing data governance insights and recommendations\n"
            "- Creating visualizations of data patterns and trends\n\n"
            "COMMUNICATION:\n"
            "- Minimize back-and-forth - use tools to resolve questions independently\n"
            "- Provide accurate, data-driven insights\n"
            "- Be proactive, not reactive\n\n"
        )

        # Add governance policy if present
        policy_section = ""
        if self.governance_policy:
            logger.info(f"Including governance policy in Llama Stack agent instructions ({len(self.governance_policy)} chars)")
            policy_section = (
                "DATA GOVERNANCE POLICY:\n"
                "The following data governance policy MUST be followed when analyzing data, "
                "making recommendations, or executing queries:\n\n"
                f"{self.governance_policy}\n\n"
                "Ensure all your responses and actions comply with the above policy. No exceptions!\n\n"
            )
        else:
            logger.info("No governance policy active - using default agent instructions")

        # Guidelines section (comprehensive from MCP-Direct)
        guidelines = (
            "IMPORTANT GUIDELINES:\n"
            "1. When a SQL query fails, use get_object_details to inspect table schemas BEFORE retrying\n"
            "2. Minimize tool calls - inspect schemas first, then construct queries carefully\n"
            "3. If you encounter repeated errors, explain the issue to the user instead of retrying endlessly\n"
            "4. When joining tables, always verify foreign key relationships using get_object_details first\n"
            "5. When considering candidate data sources for a query, always consider tables and views.\n\n"
            "FORMATTING GUIDELINES:\n"
            "6. When presenting tabular data (query results, column listings, table schemas, etc.), "
            "ALWAYS format as Markdown tables for better readability\n"
            "7. Use ```sql code blocks for SQL queries to enable syntax highlighting\n"
            "8. Use code blocks for any code snippets (Python, shell commands, etc.)\n"
            "9. Structure your responses with clear headings and sections when appropriate\n\n"
            "DATA VISUALIZATION:\n"
            "10. When appropriate, create visualizations using Vega-Lite specifications\n"
            "11. CRITICAL: Wrap Vega-Lite specs in ```vega-lite code blocks (NOT ```json)\n"
            "12. Use Vega-Lite for: trends over time, distributions, comparisons, correlations, top-N rankings\n"
            "13. Limit data in charts to 100 rows max (use aggregation or filtering in SQL)\n"
            "14. Common chart types and their mark types:\n"
            "    - Bar charts: mark='bar' (for comparisons)\n"
            "    - Line charts: mark='line' (for trends over time)\n"
            "    - Scatter plots: mark='point' (for correlations)\n"
            "    - Area charts: mark='area' (for cumulative values)\n"
            "    - Pie charts: mark='arc' with theta encoding (for proportions) - NOT mark='pie'\n"
            "15. Bar chart example:\n"
            "```vega-lite\n"
            "{\n"
            '  "$schema": "https://vega.github.io/schema/vega-lite/v5.json",\n'
            '  "data": {"values": [{"category": "A", "value": 10}, {"category": "B", "value": 20}]},\n'
            '  "mark": "bar",\n'
            '  "encoding": {\n'
            '    "x": {"field": "category", "type": "nominal"},\n'
            '    "y": {"field": "value", "type": "quantitative"}\n'
            "  }\n"
            "}\n"
            "```\n"
            "16. Pie chart example (use 'arc' mark, NOT 'pie'):\n"
            "```vega-lite\n"
            "{\n"
            '  "$schema": "https://vega.github.io/schema/vega-lite/v5.json",\n'
            '  "data": {"values": [{"category": "A", "value": 30}, {"category": "B", "value": 70}]},\n'
            '  "mark": "arc",\n'
            '  "encoding": {\n'
            '    "theta": {"field": "value", "type": "quantitative"},\n'
            '    "color": {"field": "category", "type": "nominal"}\n'
            "  }\n"
            "}\n"
            "```\n\n"
            "CRITICAL TOOL CALLING RULES (LLAMA STACK SPECIFIC):\n"
            "17. When calling tools with NO parameters, you MUST use empty braces: {}\n"
            "    ✓ CORRECT: list_schemas({})\n"
            "    ✗ WRONG: list_schemas() or list_schemas(\"\")\n"
            "18. When calling tools WITH parameters, provide them as JSON:\n"
            "    ✓ CORRECT: list_objects({\"schema_name\": \"public\", \"object_type\": \"table\"})\n"
            "19. You can ONLY make ONE tool call at a time. Never request multiple tool calls in a single response.\n"
        )

        # Add reasoning guidance
        reasoning_guidance = ""
        if enable_reasoning:
            reasoning_guidance = "\n\nThink through problems step-by-step and show your reasoning process."
        else:
            reasoning_guidance = "\n\nProvide concise, direct answers without showing intermediate reasoning steps."

        return base_content + policy_section + guidelines + reasoning_guidance

    async def delete_conversation_session(self, conversation_id: str) -> None:
        """
        Delete a conversation's Llama Stack session.

        Args:
            conversation_id: The conversation ID to delete
        """
        if conversation_id in self._session_store:
            session_id = self._session_store[conversation_id]
            logger.info(f"Deleting session {session_id} for conversation {conversation_id}")
            # TODO: Call Llama Stack API to delete session if supported
            # For now, just remove from our local store
            del self._session_store[conversation_id]
        else:
            logger.info(f"No session found for conversation {conversation_id}")

    async def cleanup(self) -> None:
        """Cleanup Llama Stack client"""
        logger.info("Cleaning up Llama Stack provider...")
        # Llama Stack client doesn't require explicit cleanup
        self._initialized = False
        self.client = None
        self.agent_id = None
        self._session_store.clear()
        logger.info("Session store cleared")

    def is_healthy(self) -> bool:
        """Check if provider is healthy"""
        return self._initialized and self.client is not None and self.agent_id is not None

    def get_tool_count(self) -> int:
        """Get number of available tools"""
        return self._tool_count

    def requires_conversation_restart_on_policy_update(self) -> bool:
        """
        Llama Stack provider REQUIRES conversation restart.

        Agent instructions are static and set at creation time. The Llama Stack
        agents API does not provide an update method, so we must recreate the
        agent to apply new policy, which invalidates all existing sessions.

        Returns:
            bool: True (restart required)
        """
        return True

    async def update_governance_policy(self, new_policy: str | None) -> None:
        """
        Update governance policy and recreate agent with new instructions.

        This is necessary because Llama Stack agents have static instructions
        that are set at creation time. The agents API does not provide an
        update method, so we must recreate the agent to apply new instructions.

        NOTE: This will invalidate all existing sessions. Users should be warned
        that their current conversations will be lost.

        Args:
            new_policy: New policy text or None to remove policy
        """
        logger.info(f"Updating governance policy - new policy length: {len(new_policy) if new_policy else 0}")

        # Update the policy
        self.governance_policy = new_policy

        # If already initialized, recreate the agent with new instructions
        if self._initialized and self.client:
            try:
                logger.info("Recreating agent with updated governance policy...")
                old_agent_id = self.agent_id

                # Create new agent with updated instructions
                agent = self.client.alpha.agents.create(
                    agent_config={
                        "model": self.llama_stack_model,
                        "instructions": self.get_system_prompt(enable_reasoning=True),
                        "toolgroups": [self.toolgroup_id],
                        "tool_choice": "auto",
                        # Llama Stack passes sampling_params directly to underlying inference engine (vLLM)
                        "sampling_params": {
                            "max_tokens": 2048,
                            "temperature": self.temperature,
                            "min_p": self.min_p,
                        }
                    }
                )
                self.agent_id = agent.agent_id
                logger.info(f"Agent recreated successfully")
                logger.info(f"  Old agent ID: {old_agent_id}")
                logger.info(f"  New agent ID: {self.agent_id}")

                # Clear session store since old sessions are tied to old agent
                logger.warning("All existing sessions invalidated - conversations must be restarted")
                self._session_store.clear()

            except Exception as e:
                logger.error(f"Failed to recreate agent with updated policy: {e}", exc_info=True)
                raise
        else:
            logger.info("Provider not initialized yet - policy will be applied on initialization")

    def get_provider_mode(self) -> str:
        """Get provider mode identifier"""
        return "llama_stack"
