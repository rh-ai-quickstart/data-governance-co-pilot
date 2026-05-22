"""
MCP-Direct Provider Implementation.

This provider manages the complete agentic loop locally, with direct connections to:
- vLLM model for LLM inference (Nemotron or Llama 3.1)
- MCP server for tool execution

Supports two tool calling formats:
- Nemotron: Custom <TOOLCALL> tags (detected from model name or explicit config)
- OpenAI: Standard function calling format (default for non-Nemotron models)
"""

import asyncio
import json
import logging
import os
import re
import time
import traceback
import uuid
from typing import Any, AsyncGenerator

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from openai import AsyncOpenAI

from .base import LLMProvider
from .tool_validation import validate_tool_call, check_mcp_server_tools, ToolValidationError

logger = logging.getLogger(__name__)


def estimate_tokens(text: str) -> int:
    """Rough token estimation: ~4 characters per token for English text"""
    return len(text) // 4


def estimate_messages_tokens(messages: list[dict]) -> dict[str, int]:
    """Estimate token usage by message role"""
    token_breakdown = {
        "system": 0,
        "user": 0,
        "assistant": 0,
        "tool": 0,
        "total": 0
    }

    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        tokens = estimate_tokens(str(content))

        if role in token_breakdown:
            token_breakdown[role] += tokens
        token_breakdown["total"] += tokens

        # Also count tool_calls if present
        if "tool_calls" in msg and msg["tool_calls"]:
            tool_calls_str = json.dumps(msg["tool_calls"])
            tool_tokens = estimate_tokens(tool_calls_str)
            token_breakdown["assistant"] += tool_tokens
            token_breakdown["total"] += tool_tokens

    return token_breakdown


class MCPDirectProvider(LLMProvider):
    """
    MCP-Direct provider: Backend manages complete agentic loop.

    Features:
    - Direct vLLM connection for LLM inference
    - Direct MCP client for tool execution
    - Model format detection (Nemotron vs OpenAI)
    - Conditional tag parsing based on model type
    - Full control over iteration logic
    - Granular event streaming
    """

    def __init__(self, config: dict[str, Any], governance_policy: str | None = None):
        """
        Initialize MCP-Direct provider.

        Args:
            config: Configuration dict with keys:
                - llm_base_url: vLLM endpoint URL
                - llm_model: Model identifier
                - llm_api_key: API key (optional for vLLM)
                - llm_max_context_length: Context window size
                - llm_tool_call_format: Tool calling format (auto/nemotron/openai)
                - llm_temperature: Sampling temperature (0.0-2.0)
                - llm_min_p: Min-P sampling threshold (0.0-1.0)
                - mcp_server_url: MCP server endpoint
            governance_policy: Optional governance policy text to include in system prompt
        """
        self.config = config
        self.governance_policy = governance_policy

        # LLM Configuration
        self.llm_base_url = config.get("llm_base_url", "http://nemotron-service:8000/v1")
        self.llm_model = config.get("llm_model", "nvidia/nemotron-nano-9b-v2")
        self.llm_api_key = config.get("llm_api_key", "not-needed")
        self.max_context_length = int(config.get("llm_max_context_length", "32768"))

        # Sampling Parameters
        self.temperature = float(config.get("llm_temperature", 0.1))
        self.min_p = float(config.get("llm_min_p", 0.1))

        # Model format detection
        self.tool_call_format = self._detect_tool_call_format(config)
        logger.info(f"Tool call format detected/configured: {self.tool_call_format}")

        # MCP Configuration
        self.mcp_server_url = config.get("mcp_server_url", "http://pg-airman-mcp-service:8000") + "/mcp"

        # Initialize OpenAI client for vLLM with generous timeout
        self.llm_client = AsyncOpenAI(
            base_url=self.llm_base_url,
            api_key=self.llm_api_key,
            timeout=600.0  # 10 minute timeout for LLM inference
        )

        # MCP session management
        self.mcp_session: ClientSession | None = None
        self.mcp_tools: list[dict[str, Any]] = []
        self._mcp_read = None
        self._mcp_write = None
        self._mcp_client_context = None
        self._mcp_session_context = None

    def _detect_tool_call_format(self, config: dict[str, Any]) -> str:
        """
        Detect tool calling format from model name or explicit configuration.

        Args:
            config: Configuration dict

        Returns:
            str: "nemotron" or "openai"
        """
        # Explicit configuration takes precedence
        explicit_format = config.get("llm_tool_call_format", "auto")
        if explicit_format and explicit_format != "auto":
            logger.info(f"Using explicit tool call format: {explicit_format}")
            return explicit_format

        # Auto-detect from model name
        model_name = config.get("llm_model", "").lower()
        if "nemotron" in model_name:
            logger.info(f"Auto-detected Nemotron model from name: {config.get('llm_model')}")
            return "nemotron"

        logger.info(f"Auto-detected OpenAI format for model: {config.get('llm_model')}")
        return "openai"

    async def _retry_mcp_operation(self, operation, operation_name: str, max_retries: int = 3):
        """
        Retry an MCP operation with exponential backoff.

        Handles transient failures when connecting to MCP server:
        - Connection errors
        - Temporary unavailability
        - Network issues

        Args:
            operation: Async function to execute
            operation_name: Name for logging
            max_retries: Maximum number of retry attempts

        Returns:
            Result from the operation

        Raises:
            Last exception if all retries fail
        """
        import asyncio

        delay = 1.0  # Initial delay in seconds
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                return await operation()
            except Exception as e:
                last_error = e
                # Get error details - handle empty error messages
                error_msg = str(e) if str(e) else repr(e)
                error_type = type(e).__name__

                if attempt < max_retries:
                    logger.warning(
                        f"MCP {operation_name} failed (attempt {attempt + 1}/{max_retries + 1}): "
                        f"{error_type}: {error_msg}. Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, 10.0)  # Exponential backoff, max 10s
                else:
                    logger.error(
                        f"MCP {operation_name} failed after {max_retries + 1} attempts: "
                        f"{error_type}: {error_msg}",
                        exc_info=True  # Include full traceback
                    )
                    raise

        # Should never reach here, but for type safety
        raise last_error

    async def initialize(self) -> None:
        """Initialize MCP connection and discover tools with retry logic"""
        logger.info(f"Connecting to pg-airman-mcp at {self.mcp_server_url}...")

        async def connect_to_mcp():
            # Connect to MCP server - store contexts to keep connection alive
            self._mcp_client_context = streamablehttp_client(self.mcp_server_url)
            self._mcp_read, self._mcp_write, _ = await self._mcp_client_context.__aenter__()

            self._mcp_session_context = ClientSession(self._mcp_read, self._mcp_write)
            self.mcp_session = await self._mcp_session_context.__aenter__()

            await self.mcp_session.initialize()
            logger.info("Connected to pg-airman-mcp server!")

            # Discover available tools
            tools_response = await self.mcp_session.list_tools()
            logger.info(f"Discovered {len(tools_response.tools)} MCP tools")

            return tools_response

        # Retry connection with exponential backoff (covers pod startup scenarios)
        tools_response = await self._retry_mcp_operation(
            connect_to_mcp,
            "connection",
            max_retries=5  # Up to ~31 seconds total (1+2+4+8+10)
        )

        # Convert MCP tools to OpenAI function calling format
        self.mcp_tools = self._convert_mcp_tools_to_openai(tools_response.tools)

        # Security: Validate MCP server's advertised tools against our allowlist
        advertised_tool_names = [tool["function"]["name"] for tool in self.mcp_tools]
        check_mcp_server_tools(advertised_tool_names)

    def _convert_mcp_tools_to_openai(self, mcp_tools) -> list[dict[str, Any]]:
        """
        Convert MCP tool definitions to OpenAI function calling format.

        MCP tools have: name, description, inputSchema
        OpenAI expects: type="function", function={name, description, parameters}
        """
        openai_tools = []

        for tool in mcp_tools:
            openai_tool = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.inputSchema if hasattr(tool, 'inputSchema') else {
                        "type": "object",
                        "properties": {}
                    }
                }
            }
            openai_tools.append(openai_tool)

        return openai_tools

    def _parse_nemotron_tool_calls(self, content: str) -> list[dict[str, Any]]:
        """
        Parse tool calls from Nemotron's custom <TOOLCALL> tag format.

        vLLM with Nemotron outputs tool calls as:
        <TOOLCALL>[{"name": "tool_name", "arguments": {...}}]</TOOLCALL>

        This method extracts and converts them to OpenAI-compatible format.
        """
        if not content:
            return []

        # Match <TOOLCALL>...</TOOLCALL> tags
        toolcall_pattern = r'<TOOLCALL>(.*?)</TOOLCALL>'
        matches = re.findall(toolcall_pattern, content, re.DOTALL)

        if not matches:
            return []

        tool_calls = []
        for match in matches:
            try:
                # Parse the JSON array inside the tags
                calls_data = json.loads(match.strip())

                # Handle both single object and array formats
                if not isinstance(calls_data, list):
                    calls_data = [calls_data]

                for call in calls_data:
                    tool_call = {
                        "id": f"call_{uuid.uuid4().hex[:24]}",
                        "type": "function",
                        "function": {
                            "name": call["name"],
                            "arguments": json.dumps(call["arguments"])
                        }
                    }
                    tool_calls.append(tool_call)
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to parse Nemotron tool call: {e}")
                continue

        return tool_calls

    def _clean_response_text(self, content: str) -> str:
        """
        Clean LLM response by removing internal thinking tags and other artifacts.

        Removes:
        - <think>...</think> tags (LLM internal reasoning)
        - <TOOLCALL>...</TOOLCALL> tags (already parsed separately)
        - Orphan </think> tags (when LLM outputs thinking without opening tag)
        """
        if not content:
            return ""

        logger.debug(f"Original content length: {len(content)}")
        logger.debug(f"Content preview:\n{content}")

        # Remove <think>...</think> tags and their content (properly paired)
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL | re.IGNORECASE)

        # Handle case where LLM outputs thinking without opening <think> tag
        # If we find </think>, remove everything before it
        if '</think>' in content.lower():
            # Split on </think> and take everything after the last occurrence
            parts = re.split(r'</think>', content, flags=re.IGNORECASE)
            if len(parts) > 1:
                # Take everything after the last </think> tag
                content = parts[-1]

        # Remove <TOOLCALL>...</TOOLCALL> tags (already parsed)
        content = re.sub(r'<TOOLCALL>.*?</TOOLCALL>', '', content, flags=re.DOTALL | re.IGNORECASE)

        # Remove extra whitespace and trim
        content = re.sub(r'\n\s*\n', '\n\n', content)
        content = content.strip()

        logger.debug(f"Cleaned content length: {len(content)}")
        logger.debug(f"Cleaned content:\n{content}")

        return content

    def get_system_prompt(self, enable_reasoning: bool = True) -> str:
        """
        Build system prompt with optional governance policy.

        Args:
            enable_reasoning: Whether to include reasoning instructions

        Returns:
            Complete system prompt string with policy (if present) and formatting guidelines
        """
        # Base prompt content
        base_content = (
            "ROLE: You are a data analyst with PostgreSQL database access via MCP tools.\n\n"

            "GOVERNANCE (HIGHEST PRIORITY):\n"
            "- Data governance policy rules ALWAYS override user requests - no exceptions\n"
            "- Enforce policy rules in SQL (data masking, row limits, access restrictions) not post-processing\n"
            "- Refuse queries that violate policy, even when users insist\n\n"

            "TOOL USAGE:\n"
            "- Proactively explore schema, relationships, and constraints without asking permission\n"
            "- Try multiple query variations if initial attempts fail\n"
            "- Resolve ambiguity using tools first, not by asking users for clarification\n"
            "- Infer table/view/column names - don't expect users to provide exact names\n\n"

            "DATABASE EXPLORATION:\n"
            "- Broad queries: List all object types (tables, views) across schemas first\n"
            "- Describe requests: Summarize key objects with purpose and sensitivity (PII, deprecated)\n"
            "- Infer relationships: Identify foreign keys, star schema patterns, data flow\n"
            "- Always surface governance rules (PII restrictions, deprecated objects) upfront\n\n"

            "COMMUNICATION:\n"
            "- Minimize back-and-forth - use tools to resolve questions independently\n"
            "- Provide accurate, data-driven insights\n"
            "- Be proactive, not reactive\n\n"
        )

        # Add governance policy if present
        policy_section = ""
        if self.governance_policy:
            logger.info(f"Including governance policy in system prompt ({len(self.governance_policy)} chars)")
            policy_section = (
                "DATA GOVERNANCE POLICY:\n"
                "The following data governance policy MUST be followed when analyzing data, "
                "making recommendations, or executing queries:\n\n"
                f"{self.governance_policy}\n\n"
                "Ensure all your responses and actions comply with the above policy. No exceptions!\n\n"
            )
        else:
            logger.info("No governance policy active - using default system prompt")

        # Guidelines section
        guidelines = (
            "IMPORTANT GUIDELINES:\n"
            "1. When a SQL query fails, use get_object_details to inspect table schemas BEFORE retrying\n"
            "2. Minimize tool calls - inspect schemas first, then construct queries carefully\n"
            "3. If you encounter repeated errors, explain the issue to the user instead of retrying endlessly\n"
            "4. When joining tables, always verify foreign key relationships using get_object_details first\n"
            "5. When considering candidate data sources for a query, always consider tables and views.\n\n"
            "TOOL-SPECIFIC GUIDELINES:\n"
            "- explain_query tool: Pass ONLY the SELECT query (e.g., 'SELECT * FROM table')\n"
            "  DO NOT include EXPLAIN or EXPLAIN ANALYZE in the sql parameter - the tool adds those automatically\n"
            "  IMPORTANT: ALWAYS use analyze=false due to database security restrictions\n"
            "  analyze=true is blocked by the database (EXPLAIN ANALYZE not permitted in restricted mode)\n"
            "  WRONG: {\"sql\": \"EXPLAIN SELECT * FROM table\", \"analyze\": true}\n"
            "  CORRECT: {\"sql\": \"SELECT * FROM table\", \"analyze\": false, \"hypothetical_indexes\": []}\n"
            "  The tool returns a JSON query plan with ESTIMATED metrics (not actual timing):\n"
            "  * Total Cost (cost units, not milliseconds)\n"
            "  * Plan Rows (estimated row count)\n"
            "  * Node Type (Seq Scan, Index Scan, Hash Join, etc.)\n"
            "  * Startup Cost vs Total Cost\n"
            "  Extract these insights and explain performance implications in plain language\n"
            "  Note: Without analyze=true, you get ESTIMATES not ACTUALS - make this clear to users\n\n"
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
            "```"
        )

        # Reasoning instruction (only for Nemotron - uses native /think tags)
        reasoning_instruction = ""
        if self.tool_call_format == "nemotron" and enable_reasoning:
            reasoning_instruction = "\n\n/think"
        elif self.tool_call_format == "nemotron" and not enable_reasoning:
            reasoning_instruction = "\n\n/no_think"

        return base_content + policy_section + guidelines + reasoning_instruction

    async def process_query_stream(
        self,
        user_query: str,
        conversation_id: str | None,
        enable_reasoning: bool,
        messages: list[dict] | None = None
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Process user query through LLM with MCP tool support, streaming progress events.

        Yields SSE events for:
        - iteration_start: When a new iteration begins
        - llm_thinking: LLM's internal reasoning (from <think> tags)
        - llm_content_delta: Streaming LLM response text
        - tool_call: When a tool is being executed
        - tool_result: Tool execution complete (timing info only)
        - final_response: The final answer
        - error: If an error occurs

        Args:
            user_query: The user's question or request
            conversation_id: Optional conversation ID for maintaining context
            enable_reasoning: Whether to include reasoning in responses
            messages: Optional pre-populated message history
        """
        try:
            # Start overall timing
            query_start_time = time.time()
            total_llm_time = 0.0
            total_mcp_time = 0.0

            # Log current MCP session ID to track if sessions are being reused
            logger.info(f"Processing query with MCP session {id(self.mcp_session)}")

            yield {
                "type": "query_start",
                "query": user_query,
                "timestamp": time.strftime('%H:%M:%S')
            }

            # Initialize conversation messages if not provided
            if messages is None:
                messages = [
                    {
                        "role": "system",
                        "content": self.get_system_prompt(enable_reasoning=enable_reasoning)
                    }
                ]

            # Add user query to conversation
            messages.append({
                "role": "user",
                "content": user_query
            })

            tool_calls_made = []
            max_iterations = 100
            iteration = 0

            while iteration < max_iterations:
                iteration += 1

                yield {
                    "type": "iteration_start",
                    "iteration": iteration,
                    "max_iterations": max_iterations
                }

                # Estimate and log token usage
                token_breakdown = estimate_messages_tokens(messages)
                tools_tokens = estimate_tokens(json.dumps(self.mcp_tools, default=str))
                total_with_tools = token_breakdown['total'] + tools_tokens

                logger.debug(f"Iteration {iteration} - Estimated tokens: {total_with_tools:,}/{self.max_context_length:,} ({(total_with_tools/self.max_context_length*100):.1f}%)")

                if total_with_tools > self.max_context_length:
                    logger.warning(f"Token estimate ({total_with_tools:,}) exceeds model limit ({self.max_context_length:,})!")

                # Call LLM with streaming mode
                llm_start = time.time()
                try:
                    # Build API call parameters
                    # IMPORTANT: Always include tools regardless of format
                    # Format only affects how we PARSE tool calls from the response
                    # (Nemotron uses <TOOLCALL> tags, OpenAI uses function calling)
                    api_params = {
                        "model": self.llm_model,
                        "messages": messages,
                        "tools": self.mcp_tools,
                        "tool_choice": "auto",
                        "max_tokens": 2048,
                        "temperature": self.temperature,
                        "stream": True,
                        # Pass vLLM-specific parameters via extra_body
                        # min_p is not part of standard OpenAI API but supported by vLLM
                        # See: https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html
                        "extra_body": {
                            "min_p": self.min_p
                        }
                    }

                    #logger.debug(f"Messages being sent to LLM:\n{json.dumps(messages, indent=2)}")
                    stream = await self.llm_client.chat.completions.create(**api_params)

                    # Stream response while handling thinking content
                    accumulated_content = ""
                    # For Nemotron, always process thinking tags (skip until first </think>)
                    # enable_reasoning only determines if we SHOW thinking to user or silently discard it
                    first_close_tag_found = False if self.tool_call_format == "nemotron" else True
                    inside_think_tag = False
                    content_buffer = ""

                    # Accumulate OpenAI-format tool calls from streaming delta
                    # Tool calls are streamed incrementally by index, need to accumulate arguments
                    accumulated_tool_calls = {}

                    async for chunk in stream:
                        delta = chunk.choices[0].delta

                        # Process OpenAI-format tool calls (Llama 3.1, Qwen3 style)
                        if self.tool_call_format == "openai" and hasattr(delta, 'tool_calls') and delta.tool_calls:
                            # Tool calls in delta - accumulate by index
                            logger.debug(f"Received tool_calls in delta: {delta.tool_calls}")
                            for tc in delta.tool_calls:
                                index = tc.index
                                if index not in accumulated_tool_calls:
                                    # Initialize new tool call
                                    accumulated_tool_calls[index] = {
                                        "id": tc.id,
                                        "type": tc.type,
                                        "function": {
                                            "name": tc.function.name if tc.function.name else "",
                                            "arguments": ""
                                        }
                                    }
                                # Accumulate arguments (streamed incrementally)
                                if tc.function.arguments:
                                    accumulated_tool_calls[index]["function"]["arguments"] += tc.function.arguments

                        # Process content
                        if delta.content:
                            content_buffer += delta.content
                            logger.debug(f"Received chunk: {repr(delta.content[:100])}, buffer size: {len(content_buffer)}")

                            # Process buffer (same streaming logic as before)
                            while content_buffer:
                                # Check for <TOOLCALL> tag FIRST (Nemotron format only)
                                # This must come before thinking tag checks to prevent thinking logic
                                # from consuming toolcall content when reasoning is disabled
                                if self.tool_call_format == "nemotron":
                                    toolcall_start = content_buffer.lower().find('<toolcall>')
                                    if toolcall_start != -1:
                                        if content_buffer[:toolcall_start]:
                                            accumulated_content += content_buffer[:toolcall_start]
                                            yield {
                                                "type": "llm_content_delta",
                                                "content": content_buffer[:toolcall_start],
                                                "iteration": iteration
                                            }
                                        toolcall_end = content_buffer.lower().find('</toolcall>', toolcall_start)
                                        if toolcall_end != -1:
                                            toolcall_block = content_buffer[toolcall_start:toolcall_end + 11]
                                            accumulated_content += toolcall_block
                                            content_buffer = content_buffer[toolcall_end + 11:]
                                        else:
                                            if len(content_buffer) > 11:
                                                to_keep = content_buffer[toolcall_start:]
                                                accumulated_content += content_buffer[:toolcall_start]
                                                content_buffer = to_keep
                                            break
                                        continue

                                if self.tool_call_format == "nemotron" and not first_close_tag_found and enable_reasoning:
                                    # Nemotron format: handle first thinking block (before first </think>)
                                    # ONLY when reasoning is enabled (when disabled, there are no thinking tags)
                                    close_idx = content_buffer.lower().find('</think>')
                                    if close_idx != -1:
                                        if content_buffer[:close_idx]:
                                            yield {
                                                "type": "llm_thinking",
                                                "content": content_buffer[:close_idx],
                                                "iteration": iteration
                                            }
                                        first_close_tag_found = True
                                        content_buffer = content_buffer[close_idx + 8:]
                                    else:
                                        if len(content_buffer) > 8:
                                            to_send = content_buffer[:-8]
                                            content_buffer = content_buffer[-8:]
                                            yield {
                                                "type": "llm_thinking",
                                                "content": to_send,
                                                "iteration": iteration
                                            }
                                        break
                                elif inside_think_tag:
                                    close_idx = content_buffer.lower().find('</think>')
                                    if close_idx != -1:
                                        if content_buffer[:close_idx] and enable_reasoning:
                                            yield {
                                                "type": "llm_thinking",
                                                "content": content_buffer[:close_idx],
                                                "iteration": iteration
                                            }
                                        inside_think_tag = False
                                        content_buffer = content_buffer[close_idx + 8:]
                                    else:
                                        if len(content_buffer) > 8:
                                            to_send = content_buffer[:-8]
                                            content_buffer = content_buffer[-8:]
                                            if enable_reasoning:
                                                yield {
                                                    "type": "llm_thinking",
                                                    "content": to_send,
                                                    "iteration": iteration
                                                }
                                        break
                                else:
                                    # Check for <think> tag (Nemotron format only)
                                    # Always check for <think> tags in Nemotron format, regardless of enable_reasoning
                                    # enable_reasoning only controls if we SHOW the thinking content to user
                                    if self.tool_call_format == "nemotron":
                                        open_idx = content_buffer.lower().find('<think>')
                                        if open_idx != -1:
                                            if content_buffer[:open_idx]:
                                                accumulated_content += content_buffer[:open_idx]
                                                yield {
                                                    "type": "llm_content_delta",
                                                    "content": content_buffer[:open_idx],
                                                    "iteration": iteration
                                                }
                                            content_buffer = content_buffer[open_idx + 7:]
                                            inside_think_tag = True
                                            continue

                                    # No tags - send content
                                    if len(content_buffer) > 11:
                                        to_send = content_buffer[:-11]
                                        content_buffer = content_buffer[-11:]
                                        accumulated_content += to_send
                                        yield {
                                            "type": "llm_content_delta",
                                            "content": to_send,
                                            "iteration": iteration
                                        }
                                    break

                    # Flush remaining buffer
                    if content_buffer:
                        logger.debug(f"Flushing remaining buffer ({len(content_buffer)} chars)")
                        if self.tool_call_format == "nemotron" and not first_close_tag_found:
                            # Nemotron format: waiting for first </think> tag
                            # If reasoning is disabled and we never found </think>, this is normal content
                            # (Nemotron honored /no_think and didn't generate thinking tags)
                            if enable_reasoning:
                                # Reasoning enabled: treat as thinking content
                                yield {
                                    "type": "llm_thinking",
                                    "content": content_buffer,
                                    "iteration": iteration
                                }
                            else:
                                # Reasoning disabled: /no_think worked, this is normal content
                                accumulated_content += content_buffer
                                yield {
                                    "type": "llm_content_delta",
                                    "content": content_buffer,
                                    "iteration": iteration
                                }
                        elif inside_think_tag:
                            # Inside think tag - only show if reasoning enabled
                            if enable_reasoning:
                                yield {
                                    "type": "llm_thinking",
                                    "content": content_buffer,
                                    "iteration": iteration
                                }
                        else:
                            accumulated_content += content_buffer
                            yield {
                                "type": "llm_content_delta",
                                "content": content_buffer,
                                "iteration": iteration
                            }
                        content_buffer = ""

                    llm_elapsed = time.time() - llm_start
                    total_llm_time += llm_elapsed

                    # Parse tool calls based on format
                    if self.tool_call_format == "nemotron":
                        parsed_tool_calls = self._parse_nemotron_tool_calls(accumulated_content)
                    else:
                        # OpenAI format - use accumulated tool calls from streaming delta
                        # Convert dict to list, sorted by index to maintain order
                        parsed_tool_calls = [
                            accumulated_tool_calls[idx]
                            for idx in sorted(accumulated_tool_calls.keys())
                        ] if accumulated_tool_calls else []
                        logger.debug(f"Accumulated {len(parsed_tool_calls)} tool calls from OpenAI format stream")
                        if parsed_tool_calls:
                            logger.debug(f"Tool calls: {parsed_tool_calls}")

                    cleaned_content = self._clean_response_text(accumulated_content) if accumulated_content else None

                    # Create message object
                    from types import SimpleNamespace
                    message = SimpleNamespace(
                        content=cleaned_content,
                        tool_calls=[
                            SimpleNamespace(
                                id=tc["id"],
                                type=tc["type"],
                                function=SimpleNamespace(
                                    name=tc["function"]["name"],
                                    arguments=tc["function"]["arguments"]
                                )
                            )
                            for tc in parsed_tool_calls
                        ] if parsed_tool_calls else None
                    )

                except Exception as e:
                    llm_elapsed = time.time() - llm_start
                    logger.error(f"LLM call failed in iteration {iteration}: {e}")
                    logger.error(f"Full traceback:\n{traceback.format_exc()}")
                    yield {
                        "type": "error",
                        "message": f"LLM API call failed: {str(e)}",
                        "traceback": traceback.format_exc(),
                        "total_time": time.time() - query_start_time,
                        "iterations": iteration,
                        "tool_calls": len(tool_calls_made)
                    }
                    return

                # Parse tool calls
                tool_calls = message.tool_calls if message.tool_calls else []
                if not tool_calls and message.content and self.tool_call_format == "nemotron":
                    tool_calls = self._parse_nemotron_tool_calls(message.content)

                # If no tool calls, we have the final answer
                if not tool_calls:
                    cleaned_response = self._clean_response_text(message.content)

                    messages.append({
                        "role": "assistant",
                        "content": cleaned_response
                    })

                    # Calculate final context window usage
                    final_token_breakdown = estimate_messages_tokens(messages)
                    final_tools_tokens = estimate_tokens(json.dumps(self.mcp_tools, default=str))
                    final_total_tokens = final_token_breakdown['total'] + final_tools_tokens
                    context_usage_pct = (final_total_tokens / self.max_context_length) * 100

                    # Send timing summary
                    query_total_time = time.time() - query_start_time
                    backend_overhead = query_total_time - total_llm_time - total_mcp_time

                    yield {
                        "type": "timing_summary",
                        "total_time": query_total_time,
                        "llm_time": total_llm_time,
                        "mcp_time": total_mcp_time,
                        "backend_overhead": backend_overhead,
                        "iterations": iteration,
                        "tool_calls": len(tool_calls_made),
                        "context_tokens_used": final_total_tokens,
                        "context_tokens_limit": self.max_context_length,
                        "context_usage_pct": context_usage_pct
                    }

                    yield {
                        "type": "final_response",
                        "content": cleaned_response,
                        "tool_calls": tool_calls_made,
                        "conversation_id": conversation_id,
                        "messages": messages  # Return updated messages for conversation store
                    }
                    return

                # Execute tool calls
                cleaned_content = self._clean_response_text(message.content) if message.content else ""

                tool_calls_for_message = [
                    {
                        "id": tc.id if hasattr(tc, 'id') else tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc.function.name if hasattr(tc, 'function') else tc["function"]["name"],
                            "arguments": tc.function.arguments if hasattr(tc, 'function') else tc["function"]["arguments"]
                        }
                    }
                    for tc in tool_calls
                ]

                messages.append({
                    "role": "assistant",
                    "content": cleaned_content,
                    "tool_calls": tool_calls_for_message
                })

                for tool_call in tool_calls:
                    # Handle both dict and object formats
                    if isinstance(tool_call, dict):
                        tool_name = tool_call["function"]["name"]
                        tool_args = json.loads(tool_call["function"]["arguments"]) if isinstance(tool_call["function"]["arguments"], str) else tool_call["function"]["arguments"]
                        tool_call_id = tool_call["id"]
                    else:
                        tool_name = tool_call.function.name
                        tool_args = json.loads(tool_call.function.arguments)
                        tool_call_id = tool_call.id

                    # SECURITY: Validate tool call before execution
                    # This prevents prompt injection attacks from calling unauthorized tools
                    try:
                        validated_args = validate_tool_call(tool_name, tool_args)
                        logger.info(f"Tool validation passed: {tool_name}")
                    except ToolValidationError as e:
                        # Tool validation failed - reject the call
                        logger.error(f"SECURITY: Tool validation failed for {tool_name}: {e}")
                        tool_result = {
                            "error": f"Tool validation failed: {str(e)}",
                            "security_event": True
                        }

                        # Append error result to messages and continue to next tool
                        messages.append({
                            "role": "tool",
                            "content": json.dumps(tool_result),
                            "tool_call_id": tool_call_id
                        })

                        # Yield error event
                        yield {
                            "type": "tool_result",
                            "tool_name": tool_name,
                            "result": "VALIDATION_FAILED",
                            "mcp_time": 0.0,
                            "iteration": iteration
                        }

                        continue  # Skip to next tool call

                    # Use validated arguments (coerced to correct types)
                    tool_args = validated_args

                    yield {
                        "type": "tool_call",
                        "tool_name": tool_name,
                        "arguments": tool_args,
                        "iteration": iteration
                    }

                    # Execute tool via MCP with timeout and retry
                    mcp_start = time.time()
                    try:
                        logger.debug(f"Executing tool {tool_name} using MCP session {id(self.mcp_session)}")

                        async def execute_tool():
                            return await asyncio.wait_for(
                                self.mcp_session.call_tool(tool_name, tool_args),
                                timeout=300.0
                            )

                        tool_result = await self._retry_mcp_operation(
                            execute_tool,
                            f"tool_call:{tool_name}",
                            max_retries=2  # Quick retries for tool calls (1+2 seconds)
                        )
                    except asyncio.TimeoutError:
                        tool_result = {"error": f"Tool '{tool_name}' timed out after 5 minutes"}
                        logger.error(f"MCP tool call {tool_name} timed out")
                    except Exception as e:
                        error_msg = str(e)
                        error_type = type(e).__name__
                        # Check if MCP session is terminated or streams are closed
                        if "Session terminated" in error_msg or "404" in error_msg or "ClosedResourceError" in error_type:
                            logger.warning(f"MCP session terminated, attempting to reconnect and retry {tool_name}...")
                            try:
                                # Reconnect to MCP server (creates new session)
                                await self._reconnect_mcp()
                                # Retry the tool call with new session
                                tool_result = await asyncio.wait_for(
                                    self.mcp_session.call_tool(tool_name, tool_args),
                                    timeout=300.0
                                )
                                logger.info(f"Successfully reconnected and executed {tool_name}")
                            except Exception as reconnect_error:
                                tool_result = {"error": f"Tool '{tool_name}' failed after reconnection: {str(reconnect_error)}"}
                                logger.error(f"MCP tool call {tool_name} failed even after reconnection: {reconnect_error}")
                        else:
                            tool_result = {"error": f"Tool '{tool_name}' failed: {error_msg}"}
                            logger.error(f"MCP tool call {tool_name} failed after retries: {e}")

                    mcp_elapsed = time.time() - mcp_start
                    total_mcp_time += mcp_elapsed

                    tool_calls_made.append({
                        "tool": tool_name,
                        "arguments": tool_args,
                        "result": str(tool_result)
                    })

                    yield {
                        "type": "tool_result",
                        "tool_name": tool_name,
                        "mcp_time": mcp_elapsed,
                        "iteration": iteration
                    }

                    # Add tool result to conversation
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": str(tool_result)
                    })

            # Max iterations exceeded
            query_total_time = time.time() - query_start_time
            yield {
                "type": "error",
                "message": f"Query exceeded max iterations ({max_iterations})",
                "total_time": query_total_time,
                "iterations": iteration,
                "tool_calls": len(tool_calls_made)
            }

        except Exception as e:
            yield {
                "type": "error",
                "message": str(e),
                "traceback": traceback.format_exc()
            }

    async def _reconnect_mcp(self):
        """
        Reconnect to MCP server after connection loss.

        This recreates the MCP session. While it works, it does trigger warnings
        about task boundaries due to cleaning up contexts from the startup task.
        """
        old_session_id = id(self.mcp_session) if self.mcp_session else None
        logger.warning(f"MCP connection lost (old session: {old_session_id}), attempting to reconnect...")
        await self.initialize()
        logger.info(f"MCP reconnection successful! New session: {id(self.mcp_session)}")

    async def cleanup(self) -> None:
        """Cleanup MCP session and HTTP client"""
        logger.info("Cleaning up MCP-Direct provider...")
        if self._mcp_session_context:
            await self._mcp_session_context.__aexit__(None, None, None)
        if self._mcp_client_context:
            await self._mcp_client_context.__aexit__(None, None, None)
        logger.info("MCP-Direct provider cleanup complete")

    def is_healthy(self) -> bool:
        """Check if provider is healthy"""
        return self.mcp_session is not None

    def get_tool_count(self) -> int:
        """Get number of available tools"""
        return len(self.mcp_tools)

    def requires_conversation_restart_on_policy_update(self) -> bool:
        """
        MCP-Direct provider does NOT require conversation restart.

        System prompts are built dynamically for each request, so policy
        changes apply immediately to new messages without needing to restart
        conversations.

        Returns:
            bool: False (no restart needed)
        """
        return False

    async def update_governance_policy(self, new_policy: str | None) -> None:
        """
        Update governance policy for MCP-Direct provider.

        Simply updates the policy field - no agent recreation needed since
        system prompts are built dynamically for each request.

        Args:
            new_policy: New policy text or None to remove policy
        """
        logger.info(f"Updating governance policy - new policy length: {len(new_policy) if new_policy else 0}")
        self.governance_policy = new_policy
        logger.info("Policy updated successfully - will apply to next user message")

    def get_provider_mode(self) -> str:
        """Get provider mode identifier"""
        return "mcp_direct"
