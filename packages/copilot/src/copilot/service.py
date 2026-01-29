"""
Data Governance Copilot Service

FastAPI backend that orchestrates interactions between:
- Nemotron LLM (via OpenAI-compatible API)
- pg-airman-mcp server (PostgreSQL analysis tools)
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

# Set up logging
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

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from openai import AsyncOpenAI
from pydantic import BaseModel


class QueryRequest(BaseModel):
    """User query request model"""
    query: str
    conversation_id: str | None = None
    enable_reasoning: bool = True  # Whether to include reasoning in LLM responses


class QueryResponse(BaseModel):
    """Response model for queries"""
    response: str
    tool_calls: list[dict[str, Any]] | None = None
    conversation_id: str | None = None


class PolicyUploadRequest(BaseModel):
    """Request model for uploading governance policy"""
    policy_text: str


class PolicyResponse(BaseModel):
    """Response model for policy operations"""
    status: str
    policy_length: int | None = None
    message: str | None = None


class PolicyStatusResponse(BaseModel):
    """Response model for policy status check"""
    has_policy: bool
    policy_length: int | None = None
    policy_preview: str | None = None


class DataGovernanceCopilot:
    """
    Orchestrates LLM interactions with MCP tools.

    This class manages:
    1. Connection to pg-airman-mcp server
    2. Connection to Nemotron LLM
    3. Tool discovery and format conversion
    4. Multi-turn conversation loop with tool execution
    """

    def __init__(self):
        # LLM Configuration
        self.llm_base_url = os.getenv(
            "LLM_BASE_URL",
            "http://nemotron-service:8000/v1"
        )
        self.llm_model = os.getenv(
            "LLM_MODEL",
            "nvidia/nemotron-nano-9b-v2"
        )
        self.llm_api_key = os.getenv(
            "LLM_API_KEY",
            "not-needed"  # Default for vLLM servers that don't require auth
        )
        self.max_context_length = int(os.getenv(
            "LLM_MAX_CONTEXT_LENGTH",
            "32768"  # Default matches NVIDIA Nemotron Nano 9B v2
        ))

        # MCP Configuration
        self.mcp_server_url = os.getenv(
            "PG_AIRMAN_MCP_SERVICE_PORT",
            "http://pg-airman-mcp-service:8000"
        ) + "/mcp"

        # Initialize OpenAI client for Nemotron with generous timeout
        # timeout=600 means 600 seconds (10 minutes) for HTTP requests
        self.llm_client = AsyncOpenAI(
            base_url=self.llm_base_url,
            api_key=self.llm_api_key,
            timeout=600.0  # 10 minute timeout for LLM inference (matches route timeout)
        )

        self.mcp_session: ClientSession | None = None
        self.mcp_tools: list[dict[str, Any]] = []
        self._mcp_read = None
        self._mcp_write = None
        self._mcp_client_context = None
        self._mcp_session_context = None

    async def initialize(self):
        """Initialize MCP connection and discover tools"""
        print(f"Connecting to pg-airman-mcp at {self.mcp_server_url}...")

        # Connect to MCP server - store contexts to keep connection alive
        self._mcp_client_context = streamablehttp_client(self.mcp_server_url)
        self._mcp_read, self._mcp_write, get_session_id = await self._mcp_client_context.__aenter__()

        self._mcp_session_context = ClientSession(self._mcp_read, self._mcp_write)
        self.mcp_session = await self._mcp_session_context.__aenter__()

        await self.mcp_session.initialize()
        print("Connected to pg-airman-mcp server!")

        # Discover available tools
        tools_response = await self.mcp_session.list_tools()
        print(f"Discovered {len(tools_response.tools)} MCP tools")

        # Convert MCP tools to OpenAI function calling format
        self.mcp_tools = self._convert_mcp_tools_to_openai(tools_response.tools)

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

    def _parse_tool_calls_from_text(self, content: str) -> list[dict[str, Any]]:
        """
        Parse tool calls from vLLM text output with Hermes/Mistral format.

        vLLM with tool parsers outputs tool calls as:
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
                print(f"Warning: Failed to parse tool call: {e}")
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

        print(f"[DEBUG] Original content length: {len(content)}")
        print(f"[DEBUG] Content preview:\n{content}")

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

        print(f"[DEBUG] Cleaned content length: {len(content)}")
        print(f"[DEBUG] Cleaned content:\n{content}")

        return content

    def _build_system_prompt(self, enable_reasoning: bool = True) -> str:
        """
        Build system prompt with optional governance policy.

        Args:
            enable_reasoning: Whether to include reasoning instructions

        Returns:
            Complete system prompt string with policy (if present) and formatting guidelines
        """
        global governance_policy

        # Base prompt content
        base_content = (
            "You are a data governance assistant with access to PostgreSQL "
            "database analysis tools. Help users understand and optimize their "
            "database performance, schema design, and query patterns. "
            "When analyzing databases, use the available tools to provide "
            "accurate, data-driven insights.\n\n"
        )

        # Add governance policy if present
        policy_section = ""
        if governance_policy:
            print(f"[POLICY] Including governance policy in system prompt ({len(governance_policy)} chars)")
            policy_section = (
                "DATA GOVERNANCE POLICY:\n"
                "The following data governance policy MUST be followed when analyzing data, "
                "making recommendations, or executing queries:\n\n"
                f"{governance_policy}\n\n"
                "Ensure all your responses and actions comply with the above policy.\n\n"
            )
        else:
            print("[POLICY] No governance policy active - using default system prompt")

        # Guidelines section
        guidelines = (
            "IMPORTANT GUIDELINES:\n"
            "1. When a SQL query fails, use get_object_details to inspect table schemas BEFORE retrying\n"
            "2. Minimize tool calls - inspect schemas first, then construct queries carefully\n"
            "3. If you encounter repeated errors, explain the issue to the user instead of retrying endlessly\n"
            "4. When joining tables, always verify foreign key relationships using get_object_details first\n\n"
            "FORMATTING GUIDELINES:\n"
            "5. When presenting tabular data (query results, column listings, table schemas, etc.), "
            "ALWAYS format as Markdown tables for better readability\n"
            "6. Use ```sql code blocks for SQL queries to enable syntax highlighting\n"
            "7. Use code blocks for any code snippets (Python, shell commands, etc.)\n"
            "8. Structure your responses with clear headings and sections when appropriate"
        )

        # Reasoning instruction (conditional)
        reasoning_instruction = ""
        if not enable_reasoning:
            reasoning_instruction = (
                "\n\nRESPONSE FORMAT:\n"
                "- Provide direct, concise answers without showing your thinking process\n"
                "- Do NOT use <think> tags or explain your reasoning steps\n"
                "- Focus on delivering the final answer immediately\n"
            )

        return base_content + policy_section + guidelines + reasoning_instruction

    async def process_query_stream(self, user_query: str, conversation_id: str | None = None, enable_reasoning: bool = True) -> AsyncGenerator[dict[str, Any], None]:
        """
        Process user query through LLM with MCP tool support, streaming progress events.

        Yields SSE events for:
        - iteration_start: When a new iteration begins
        - llm_thinking: LLM's internal reasoning (from <think> tags)
        - tool_call: When a tool is being executed
        - tool_result: Results from tool execution
        - final_response: The final answer
        - error: If an error occurs

        Args:
            user_query: The user's question or request
            conversation_id: Optional conversation ID for maintaining context across queries
        """
        try:
            # Start overall timing
            query_start_time = time.time()
            total_llm_time = 0.0
            total_mcp_time = 0.0

            yield {
                "type": "query_start",
                "query": user_query,
                "timestamp": time.strftime('%H:%M:%S')
            }

            # Get or create conversation history
            if conversation_id and conversation_id in conversation_store:
                messages = conversation_store[conversation_id].copy()
                yield {
                    "type": "conversation_resumed",
                    "conversation_id": conversation_id,
                    "message_count": len(messages)
                }
            else:
                # Start new conversation with system prompt (including policy if present)
                messages = [
                    {
                        "role": "system",
                        "content": self._build_system_prompt(enable_reasoning=enable_reasoning)
                    }
                ]
                if conversation_id:
                    conversation_store[conversation_id] = messages
                    yield {
                        "type": "conversation_started",
                        "conversation_id": conversation_id
                    }

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

                # Estimate and log token usage before LLM call (including MCP tools schema)
                token_breakdown = estimate_messages_tokens(messages)
                tools_tokens = estimate_tokens(json.dumps(self.mcp_tools, default=str))
                total_with_tools = token_breakdown['total'] + tools_tokens

                print(f"[CONTEXT] Iteration {iteration} - Estimated tokens by role:")
                print(f"  System: {token_breakdown['system']:,} tokens")
                print(f"  User: {token_breakdown['user']:,} tokens")
                print(f"  Assistant: {token_breakdown['assistant']:,} tokens")
                print(f"  Tool results: {token_breakdown['tool']:,} tokens")
                print(f"  MCP Tools schema: {tools_tokens:,} tokens ({len(self.mcp_tools)} tools)")
                print(f"  TOTAL: {total_with_tools:,} tokens (limit: {self.max_context_length:,}) - {(total_with_tools/self.max_context_length*100):.1f}% used")

                if total_with_tools > self.max_context_length:
                    print(f"[CONTEXT] ⚠️  WARNING: Token estimate ({total_with_tools:,}) exceeds model limit ({self.max_context_length:,})!")

                # ===== START [LLM_MESSAGE_DEBUG] - Can be disabled to reduce log verbosity =====
                print(f"[LLM_MESSAGE_DEBUG] Iteration {iteration} - Sending {len(messages)} messages to LLM:")
                for idx, msg in enumerate(messages):
                    role = msg.get('role', 'unknown')
                    content_preview = str(msg.get('content', ''))[:200] if msg.get('content') else '[no content]'
                    tool_calls_count = len(msg.get('tool_calls', [])) if msg.get('tool_calls') else 0

                    print(f"[LLM_MESSAGE_DEBUG]   Message {idx + 1}: role={role}, content_len={len(str(msg.get('content', '')))}, tool_calls={tool_calls_count}")
                    print(f"[LLM_MESSAGE_DEBUG]     Content preview: {content_preview}...")

                    if msg.get('tool_calls'):
                        for tc_idx, tc in enumerate(msg.get('tool_calls', [])):
                            tc_name = tc.get('function', {}).get('name', 'unknown') if isinstance(tc.get('function'), dict) else 'unknown'
                            print(f"[LLM_MESSAGE_DEBUG]       Tool call {tc_idx + 1}: {tc_name}")

                print(f"[LLM_MESSAGE_DEBUG] Full messages array:")
                print(f"[LLM_MESSAGE_DEBUG] {json.dumps(messages, indent=2, default=str)}")

                # Log MCP tools being sent (this consumes significant context!)
                tools_json = json.dumps(self.mcp_tools, indent=2, default=str)
                tools_chars = len(tools_json)
                tools_tokens = estimate_tokens(tools_json)
                print(f"[LLM_MESSAGE_DEBUG] MCP Tools parameter:")
                print(f"[LLM_MESSAGE_DEBUG]   Tool count: {len(self.mcp_tools)}")
                print(f"[LLM_MESSAGE_DEBUG]   Tools JSON size: {tools_chars:,} characters (~{tools_tokens:,} tokens)")
                print(f"[LLM_MESSAGE_DEBUG]   Tool names: {[t.get('function', {}).get('name', 'unknown') for t in self.mcp_tools]}")
                print(f"[LLM_MESSAGE_DEBUG] Full tools array:")
                print(f"[LLM_MESSAGE_DEBUG] {tools_json}")
                # ===== END [LLM_MESSAGE_DEBUG] =====

                # Call LLM with available tools
                # Send heartbeat events to keep SSE connection alive during long LLM calls
                llm_start = time.time()
                try:
                    # Create the LLM call as a background task
                    llm_task = asyncio.create_task(
                        self.llm_client.chat.completions.create(
                            model=self.llm_model,
                            messages=messages,
                            tools=self.mcp_tools,
                            tool_choice="auto",
                            max_tokens=2048,
                            temperature=0.1,
                            top_p=0.95,
                        )
                    )

                    # Send heartbeat events every 10 seconds while waiting
                    while not llm_task.done():
                        try:
                            await asyncio.wait_for(asyncio.shield(llm_task), timeout=10.0)
                        except asyncio.TimeoutError:
                            # Send heartbeat to keep connection alive
                            elapsed = time.time() - llm_start
                            yield {
                                "type": "llm_progress",
                                "message": f"LLM thinking... ({elapsed:.0f}s)",
                                "iteration": iteration
                            }

                    response = await llm_task
                    llm_elapsed = time.time() - llm_start
                    total_llm_time += llm_elapsed

                    message = response.choices[0].message
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

                # Extract thinking content if present
                if message.content:
                    thinking_content = None

                    # First try to find properly paired <think>...</think> tags
                    think_pattern = r'<think>(.*?)</think>'
                    think_matches = re.findall(think_pattern, message.content, re.DOTALL | re.IGNORECASE)

                    if think_matches:
                        # Use the first matched thinking content
                        thinking_content = think_matches[0].strip()
                    elif '</think>' in message.content.lower():
                        # Handle orphan </think> tag (LLM sometimes outputs thinking without opening tag)
                        # Extract everything before the </think> tag as thinking content
                        parts = re.split(r'</think>', message.content, flags=re.IGNORECASE)
                        if len(parts) > 1 and parts[0].strip():
                            thinking_content = parts[0].strip()

                    if thinking_content:
                        yield {
                            "type": "llm_thinking",
                            "content": thinking_content,
                            "iteration": iteration,
                            "llm_time": llm_elapsed
                        }

                # Parse tool calls from message
                tool_calls = message.tool_calls if message.tool_calls else []
                print(f"[DEBUG] message.tool_calls: {tool_calls}")
                if not tool_calls and message.content:
                    tool_calls = self._parse_tool_calls_from_text(message.content)
                    print(f"[DEBUG] Parsed tool_calls from text: {tool_calls}")

                # If no tool calls, we have the final answer
                if not tool_calls:
                    print(f"[DEBUG] No tool calls found, treating as final answer")
                    cleaned_response = self._clean_response_text(message.content)

                    # Save assistant response to conversation history
                    messages.append({
                        "role": "assistant",
                        "content": cleaned_response
                    })

                    # Update conversation store
                    if conversation_id:
                        conversation_store[conversation_id] = messages

                    # Calculate final context window usage (including MCP tools schema)
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

                    # Send final response
                    yield {
                        "type": "final_response",
                        "content": cleaned_response,
                        "tool_calls": tool_calls_made,
                        "conversation_id": conversation_id
                    }
                    return

                # Execute tool calls via MCP
                # IMPORTANT: Clean thinking content before adding to context
                # Thinking is streamed to UI but shouldn't consume context window
                print(f"[DEBUG] Executing {len(tool_calls)} tool calls")
                cleaned_content = self._clean_response_text(message.content) if message.content else ""

                print(f"[DEBUG] Building tool_calls structure for messages array")
                try:
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
                    print(f"[DEBUG] Tool calls structure built successfully")
                except Exception as e:
                    print(f"[DEBUG] Error building tool_calls structure: {e}")
                    raise

                messages.append({
                    "role": "assistant",
                    "content": cleaned_content,
                    "tool_calls": tool_calls_for_message
                })

                print(f"[DEBUG] Starting tool execution loop")
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

                    yield {
                        "type": "tool_call",
                        "tool_name": tool_name,
                        "arguments": tool_args,
                        "iteration": iteration
                    }

                    # Execute tool via MCP with timeout
                    mcp_start = time.time()
                    try:
                        # 5 minute timeout per tool call
                        tool_result = await asyncio.wait_for(
                            self.mcp_session.call_tool(tool_name, tool_args),
                            timeout=300.0
                        )
                    except asyncio.TimeoutError:
                        tool_result = {"error": f"Tool '{tool_name}' timed out after 5 minutes"}
                        logger.error(f"MCP tool call {tool_name} timed out")

                    mcp_elapsed = time.time() - mcp_start
                    total_mcp_time += mcp_elapsed

                    # Track tool calls for response
                    tool_calls_made.append({
                        "tool": tool_name,
                        "arguments": tool_args,
                        "result": str(tool_result)
                    })

                    yield {
                        "type": "tool_result",
                        "tool_name": tool_name,
                        "result": str(tool_result)[:500],  # Truncate for streaming
                        "mcp_time": mcp_elapsed,
                        "iteration": iteration
                    }

                    # Log tool result size
                    tool_result_str = str(tool_result)
                    tool_result_tokens = estimate_tokens(tool_result_str)
                    logger.info(f"[CONTEXT] Tool {tool_name} returned {len(tool_result_str):,} chars (~{tool_result_tokens:,} tokens)")

                    # Add tool result to conversation
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": tool_result_str
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

    async def process_query(self, user_query: str, conversation_id: str | None = None) -> dict[str, Any]:
        """
        Process user query through LLM with MCP tool support.

        Implements agentic loop:
        1. Send query to LLM with available tools
        2. If LLM wants to use tools, execute them via MCP
        3. Send tool results back to LLM
        4. Repeat until LLM returns final answer

        Args:
            user_query: The user's question or request
            conversation_id: Optional conversation ID for maintaining context across queries
        """
        # Start overall timing
        query_start_time = time.time()
        total_llm_time = 0.0
        total_mcp_time = 0.0
        print(f"\n{'='*80}")
        print(f"[TIMING] Starting query processing at {time.strftime('%H:%M:%S')}")
        print(f"[TIMING] Query: {user_query[:100]}{'...' if len(user_query) > 100 else ''}")
        print(f"{'='*80}\n")

        # Get or create conversation history
        if conversation_id and conversation_id in conversation_store:
            messages = conversation_store[conversation_id].copy()
            print(f"Resuming conversation {conversation_id} with {len(messages)} messages")
        else:
            # Start new conversation with system prompt (including policy if present)
            messages = [
                {
                    "role": "system",
                    "content": self._build_system_prompt(enable_reasoning=True)
                }
            ]
            if conversation_id:
                conversation_store[conversation_id] = messages
                print(f"Started new conversation {conversation_id}")

        # Add user query to conversation
        messages.append({
            "role": "user",
            "content": user_query
        })

        tool_calls_made = []
        max_iterations = 100  # Allow many iterations for complex multi-step reasoning
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            # Estimate and log token usage before LLM call (including MCP tools schema)
            token_breakdown = estimate_messages_tokens(messages)
            tools_tokens = estimate_tokens(json.dumps(self.mcp_tools, default=str))
            total_with_tools = token_breakdown['total'] + tools_tokens

            print(f"[CONTEXT] Iteration {iteration} - Estimated tokens by role:")
            print(f"  System: {token_breakdown['system']:,} tokens")
            print(f"  User: {token_breakdown['user']:,} tokens")
            print(f"  Assistant: {token_breakdown['assistant']:,} tokens")
            print(f"  Tool results: {token_breakdown['tool']:,} tokens")
            print(f"  MCP Tools schema: {tools_tokens:,} tokens ({len(self.mcp_tools)} tools)")
            print(f"  TOTAL: {total_with_tools:,} tokens (limit: {self.max_context_length:,}) - {(total_with_tools/self.max_context_length*100):.1f}% used")

            if total_with_tools > self.max_context_length:
                print(f"[CONTEXT] ⚠️  WARNING: Token estimate ({total_with_tools:,}) exceeds model limit ({self.max_context_length:,})!")

            # ===== START [LLM_MESSAGE_DEBUG] - Can be disabled to reduce log verbosity =====
            print(f"[LLM_MESSAGE_DEBUG] Iteration {iteration} - Sending {len(messages)} messages to LLM:")
            for idx, msg in enumerate(messages):
                role = msg.get('role', 'unknown')
                content_preview = str(msg.get('content', ''))[:200] if msg.get('content') else '[no content]'
                tool_calls_count = len(msg.get('tool_calls', [])) if msg.get('tool_calls') else 0

                print(f"[LLM_MESSAGE_DEBUG]   Message {idx + 1}: role={role}, content_len={len(str(msg.get('content', '')))}, tool_calls={tool_calls_count}")
                print(f"[LLM_MESSAGE_DEBUG]     Content preview: {content_preview}...")

                if msg.get('tool_calls'):
                    for tc_idx, tc in enumerate(msg.get('tool_calls', [])):
                        tc_name = tc.get('function', {}).get('name', 'unknown') if isinstance(tc.get('function'), dict) else 'unknown'
                        print(f"[LLM_MESSAGE_DEBUG]       Tool call {tc_idx + 1}: {tc_name}")

            print(f"[LLM_MESSAGE_DEBUG] Full messages array:")
            print(f"[LLM_MESSAGE_DEBUG] {json.dumps(messages, indent=2, default=str)}")

            # Log MCP tools being sent (this consumes significant context!)
            tools_json = json.dumps(self.mcp_tools, indent=2, default=str)
            tools_chars = len(tools_json)
            tools_tokens_est = estimate_tokens(tools_json)
            print(f"[LLM_MESSAGE_DEBUG] MCP Tools parameter:")
            print(f"[LLM_MESSAGE_DEBUG]   Tool count: {len(self.mcp_tools)}")
            print(f"[LLM_MESSAGE_DEBUG]   Tools JSON size: {tools_chars:,} characters (~{tools_tokens_est:,} tokens)")
            print(f"[LLM_MESSAGE_DEBUG]   Tool names: {[t.get('function', {}).get('name', 'unknown') for t in self.mcp_tools]}")
            print(f"[LLM_MESSAGE_DEBUG] Full tools array:")
            print(f"[LLM_MESSAGE_DEBUG] {tools_json}")
            # ===== END [LLM_MESSAGE_DEBUG] =====

            # Call LLM with available tools
            print(f"[TIMING] Iteration {iteration}: Calling LLM...")
            llm_start = time.time()
            response = await self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=messages,
                tools=self.mcp_tools,
                tool_choice="auto",
                max_tokens=2048,        # Limit output length for faster generation
                temperature=0.1,        # Lower temperature = faster, more deterministic
                top_p=0.95,            # Slightly restrict sampling
            )
            llm_elapsed = time.time() - llm_start
            total_llm_time += llm_elapsed
            print(f"[TIMING] Iteration {iteration}: LLM call completed in {llm_elapsed:.2f}s (cumulative: {total_llm_time:.2f}s)")

            message = response.choices[0].message

            # Parse tool calls from message (either structured or from text)
            tool_calls = message.tool_calls if message.tool_calls else []

            # If no structured tool calls, try parsing from text content
            if not tool_calls and message.content:
                tool_calls = self._parse_tool_calls_from_text(message.content)

            # If still no tool calls, we have the final answer
            if not tool_calls:
                cleaned_response = self._clean_response_text(message.content)

                # Save assistant response to conversation history
                messages.append({
                    "role": "assistant",
                    "content": cleaned_response
                })

                # Update conversation store
                if conversation_id:
                    conversation_store[conversation_id] = messages
                    print(f"Saved conversation {conversation_id} with {len(messages)} messages")

                # Print timing summary
                query_total_time = time.time() - query_start_time
                backend_overhead = query_total_time - total_llm_time - total_mcp_time
                print(f"\n{'='*80}")
                print(f"[TIMING] Query completed successfully in {iteration} iterations")
                print(f"[TIMING] Total time: {query_total_time:.2f}s")
                print(f"[TIMING] - LLM time: {total_llm_time:.2f}s ({total_llm_time/query_total_time*100:.1f}%)")
                print(f"[TIMING] - MCP time: {total_mcp_time:.2f}s ({total_mcp_time/query_total_time*100:.1f}%)")
                print(f"[TIMING] - Backend overhead: {backend_overhead:.2f}s ({backend_overhead/query_total_time*100:.1f}%)")
                print(f"[TIMING] - Tool calls made: {len(tool_calls_made)}")
                print(f"{'='*80}\n")

                return {
                    "response": cleaned_response,
                    "tool_calls": tool_calls_made
                }

            # Execute tool calls via MCP
            # IMPORTANT: Clean thinking content before adding to context
            # Thinking is useful for logging but shouldn't consume context window
            cleaned_content = self._clean_response_text(message.content) if message.content else ""

            messages.append({
                "role": "assistant",
                "content": cleaned_content,
                "tool_calls": [
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

                print(f"[TIMING] Iteration {iteration}: Executing MCP tool '{tool_name}'...")
                mcp_start = time.time()

                # Execute tool via MCP with timeout
                try:
                    # 5 minute timeout per tool call
                    tool_result = await asyncio.wait_for(
                        self.mcp_session.call_tool(tool_name, tool_args),
                        timeout=300.0
                    )
                except asyncio.TimeoutError:
                    tool_result = {"error": f"Tool '{tool_name}' timed out after 5 minutes"}
                    logger.error(f"MCP tool call {tool_name} timed out")

                mcp_elapsed = time.time() - mcp_start
                total_mcp_time += mcp_elapsed
                print(f"[TIMING] Iteration {iteration}: MCP tool '{tool_name}' completed in {mcp_elapsed:.2f}s (cumulative: {total_mcp_time:.2f}s)")

                # Track tool calls for response
                tool_calls_made.append({
                    "tool": tool_name,
                    "arguments": tool_args,
                    "result": str(tool_result)
                })

                # Log tool result size
                tool_result_str = str(tool_result)
                tool_result_tokens = estimate_tokens(tool_result_str)
                print(f"[CONTEXT] Tool {tool_name} returned {len(tool_result_str):,} chars (~{tool_result_tokens:,} tokens)")

                # Add tool result to conversation
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": tool_result_str
                })

        # If we hit max iterations, return what we have with helpful message
        query_total_time = time.time() - query_start_time
        backend_overhead = query_total_time - total_llm_time - total_mcp_time
        print(f"\n{'='*80}")
        print(f"[TIMING] Query exceeded max iterations ({max_iterations})")
        print(f"[TIMING] Total time: {query_total_time:.2f}s")
        print(f"[TIMING] - LLM time: {total_llm_time:.2f}s ({total_llm_time/query_total_time*100:.1f}%)")
        print(f"[TIMING] - MCP time: {total_mcp_time:.2f}s ({total_mcp_time/query_total_time*100:.1f}%)")
        print(f"[TIMING] - Backend overhead: {backend_overhead:.2f}s ({backend_overhead/query_total_time*100:.1f}%)")
        print(f"[TIMING] - Tool calls made: {len(tool_calls_made)}")
        print(f"{'='*80}\n")
        print(f"WARNING: Query exceeded max iterations ({max_iterations}) with {len(tool_calls_made)} tool calls")
        return {
            "response": (
                f"I apologize, but I wasn't able to complete this query after {max_iterations} attempts. "
                "The query appears too complex for automated resolution. Here's what I tried:\n\n"
                f"- Made {len(tool_calls_made)} tool calls\n"
                "- The issue seems to involve complex table relationships\n\n"
                "Please try:\n"
                "1. Breaking the query into simpler steps\n"
                "2. Asking for schema information first\n"
                "3. Being more specific about table names and relationships"
            ),
            "tool_calls": tool_calls_made
        }


# Initialize FastAPI app
app = FastAPI(
    title="Data Governance Copilot API",
    description="Backend service for data governance copilot with LLM and MCP integration",
    version="0.1.0"
)

# Add CORS middleware for Svelte frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global copilot instance
copilot: DataGovernanceCopilot | None = None

# Conversation store: conversation_id -> list of messages
# In production, this should be replaced with a persistent store (Redis, DB, etc.)
conversation_store: dict[str, list[dict[str, str]]] = {}

# Policy store: single active policy text (in-memory only)
# Policy is included in system prompt for new conversations
# Only one policy can be active at a time - uploading a new one replaces the old one
governance_policy: str | None = None


@app.on_event("startup")
async def startup_event():
    """Initialize copilot on startup"""
    global copilot
    copilot = DataGovernanceCopilot()
    await copilot.initialize()


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "mcp_connected": copilot.mcp_session is not None if copilot else False,
        "tools_available": len(copilot.mcp_tools) if copilot else 0
    }


@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """
    Process user query through LLM with MCP tool support.

    The copilot will:
    1. Send query to Nemotron LLM
    2. Execute any requested MCP tools
    3. Return final answer with tool execution details
    """
    if not copilot:
        raise HTTPException(status_code=503, detail="Copilot not initialized")

    try:
        result = await copilot.process_query(request.query, request.conversation_id)
        return QueryResponse(
            response=result["response"],
            tool_calls=result.get("tool_calls"),
            conversation_id=request.conversation_id
        )
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"[ERROR] Query processing failed: {error_details}")
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")


@app.post("/query/stream")
async def query_stream(request: QueryRequest):
    """
    Process user query with Server-Sent Events (SSE) for real-time progress updates.

    Streams events including:
    - iteration_start: When each iteration begins
    - llm_thinking: LLM's reasoning process
    - tool_call: When tools are executed
    - tool_result: Results from tools
    - final_response: The complete answer
    - timing_summary: Performance breakdown
    - error: If something goes wrong
    """
    if not copilot:
        raise HTTPException(status_code=503, detail="Copilot not initialized")

    async def event_generator():
        """Generate SSE formatted events"""
        try:
            async for event in copilot.process_query_stream(request.query, request.conversation_id, request.enable_reasoning):
                # Format as SSE: data: {json}\n\n
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            error_event = {
                "type": "error",
                "message": str(e),
                "traceback": traceback.format_exc()
            }
            yield f"data: {json.dumps(error_event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@app.get("/tools")
async def list_tools():
    """List available MCP tools"""
    if not copilot:
        raise HTTPException(status_code=503, detail="Copilot not initialized")

    return {
        "tools": copilot.mcp_tools,
        "count": len(copilot.mcp_tools)
    }


@app.get("/conversations")
async def list_conversations():
    """List active conversations (for debugging)"""
    return {
        "conversations": [
            {
                "id": conv_id,
                "message_count": len(messages),
                "last_message": messages[-1]["content"][:100] if messages else None
            }
            for conv_id, messages in conversation_store.items()
        ],
        "total": len(conversation_store)
    }


@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation"""
    if conversation_id in conversation_store:
        del conversation_store[conversation_id]
        return {"status": "deleted", "conversation_id": conversation_id}
    else:
        raise HTTPException(status_code=404, detail="Conversation not found")


# ============================================================================
# Policy Management Endpoints
# ============================================================================

@app.post("/policy/upload", response_model=PolicyResponse)
async def upload_policy(request: PolicyUploadRequest):
    """
    Upload or replace data governance policy.
    Only one policy can be active at a time - uploading replaces the existing policy.
    Policy is included in the system prompt for new conversations.
    """
    global governance_policy

    if not request.policy_text or not request.policy_text.strip():
        raise HTTPException(status_code=400, detail="Policy text cannot be empty")

    governance_policy = request.policy_text.strip()
    print(f"[POLICY] Policy uploaded successfully - {len(governance_policy)} characters")
    print(f"[POLICY] Policy preview: {governance_policy[:200]}...")

    return PolicyResponse(
        status="uploaded",
        policy_length=len(governance_policy),
        message="Policy uploaded successfully. It will be included in new conversations."
    )


@app.delete("/policy", response_model=PolicyResponse)
async def delete_policy():
    """
    Remove the active data governance policy.
    Policy will no longer be included in new conversations.
    """
    global governance_policy

    if governance_policy is None:
        raise HTTPException(status_code=404, detail="No policy currently active")

    print("[POLICY] Policy deleted - new conversations will use default system prompt")
    governance_policy = None

    return PolicyResponse(
        status="deleted",
        policy_length=None,
        message="Policy deleted successfully. New conversations will not include the policy."
    )


@app.get("/policy/status", response_model=PolicyStatusResponse)
async def get_policy_status():
    """
    Get status of current data governance policy.
    Returns whether a policy is active and a preview of its content.
    """
    global governance_policy

    if governance_policy is None:
        return PolicyStatusResponse(
            has_policy=False,
            policy_length=None,
            policy_preview=None
        )

    return PolicyStatusResponse(
        has_policy=True,
        policy_length=len(governance_policy),
        policy_preview=governance_policy[:200] + ("..." if len(governance_policy) > 200 else "")
    )
