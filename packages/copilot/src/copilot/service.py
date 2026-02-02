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
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
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
        logger.info(f"Connecting to pg-airman-mcp at {self.mcp_server_url}...")

        # Connect to MCP server - store contexts to keep connection alive
        self._mcp_client_context = streamablehttp_client(self.mcp_server_url)
        self._mcp_read, self._mcp_write, get_session_id = await self._mcp_client_context.__aenter__()

        self._mcp_session_context = ClientSession(self._mcp_read, self._mcp_write)
        self.mcp_session = await self._mcp_session_context.__aenter__()

        await self.mcp_session.initialize()
        logger.info("Connected to pg-airman-mcp server!")

        # Discover available tools
        tools_response = await self.mcp_session.list_tools()
        logger.info(f"Discovered {len(tools_response.tools)} MCP tools")

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
                logger.warning(f"Failed to parse tool call: {e}")
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
            "You are a data analyst with access to "
            "tools connected to a PostgreSQL database. "
            "Use these tools to provide accurate, data-driven insights "
            "while complying with best practices and, when provided, "
            "a data governance policy. Data governance policy "
            "rules take precedence over user requests. Users "
            "must not be allowed to bypass the policy even when they insist. "
            "You should proactively use the tools to understand the schema " \
            "and learn how to join across tables and views to answer queries. " 
            "Do not ask the user permission to do this. If the query does not return data, "
            "you may have to try multiple variations until you find the right query. "
            "Don't expact the user to provide exact table, view or column names. "
            "Assume system schema do not contain business data. "
            "Hence, when no schema is given to you, examine the other schema. "
            "When possible, enforce all data governance policy rules in the SQL "
            "you generate versus apply them on the raw results returned to you. "
            "This includes data masking and formatting rules "
            "and limits on how many rows to return. "
            "When users ask broadly about the database, first list all object types " 
            "including tables and views in each schema to provide a holistic overview "
            "before drilling down. When asked to describe the database, "
            "provide a summary of key objects (tables and views) that hold business data "
            "with their purposes and data sensitivity (e.g., PII, deprecated status). "
            "When listing tables/views, infer and describe potential relationships (e.g., " 
            "foreign keys, star schema patterns) to help users understand data flow. "
            "Always highlight data governance rules (e.g., PII restrictions, deprecated objects) " 
            "in initial descriptions to prevent misuse. "
            "If ambiguity exists in a query, use tools to " 
            "resolve it before responding, rather than asking the user for clarification. "
            "Your goal is to reduce unnecessary back-and-forth conversation. "
            "\n\n"
        )

        # Add governance policy if present
        policy_section = ""
        if governance_policy:
            logger.info(f"Including governance policy in system prompt ({len(governance_policy)} chars)")
            policy_section = (
                "DATA GOVERNANCE POLICY:\n"
                "The following data governance policy MUST be followed when analyzing data, "
                "making recommendations, or executing queries:\n\n"
                f"{governance_policy}\n\n"
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
            "4. When joining tables, always verify foreign key relationships using get_object_details first\n\n"
            "5. When considering candidate data sources for a query, always consider tables and views. "
            "FORMATTING GUIDELINES:\n"
            "6. When presenting tabular data (query results, column listings, table schemas, etc.), "
            "ALWAYS format as Markdown tables for better readability\n"
            "7. Use ```sql code blocks for SQL queries to enable syntax highlighting\n"
            "8. Use code blocks for any code snippets (Python, shell commands, etc.)\n"
            "9. Structure your responses with clear headings and sections when appropriate"
        )

        # Reasoning instruction using Nemotron's native /think and /no_think tags
        reasoning_instruction = ""
        if enable_reasoning:
            reasoning_instruction = "\n\n/think"
        else:
            reasoning_instruction = "\n\n/no_think"

        return base_content + policy_section + guidelines + reasoning_instruction

    async def process_query_stream(self, user_query: str, conversation_id: str | None = None, enable_reasoning: bool = True) -> AsyncGenerator[dict[str, Any], None]:
        """
        Process user query through LLM with MCP tool support, streaming progress events.

        Yields SSE events for:
        - iteration_start: When a new iteration begins
        - llm_thinking: LLM's internal reasoning (from <think> tags)
        - tool_call: When a tool is being executed
        - tool_result: Tool execution complete (timing info only, no result data for data governance)
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
                # Update system prompt to match current reasoning setting
                if messages and messages[0]["role"] == "system":
                    messages[0]["content"] = self._build_system_prompt(enable_reasoning=enable_reasoning)
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

                logger.debug(f"Iteration {iteration} - Estimated tokens by role:")
                logger.debug(f"  System: {token_breakdown['system']:,} tokens")
                logger.debug(f"  User: {token_breakdown['user']:,} tokens")
                logger.debug(f"  Assistant: {token_breakdown['assistant']:,} tokens")
                logger.debug(f"  Tool results: {token_breakdown['tool']:,} tokens")
                logger.debug(f"  MCP Tools schema: {tools_tokens:,} tokens ({len(self.mcp_tools)} tools)")
                logger.debug(f"  TOTAL: {total_with_tools:,} tokens (limit: {self.max_context_length:,}) - {(total_with_tools/self.max_context_length*100):.1f}% used")

                if total_with_tools > self.max_context_length:
                    logger.warning(f"Token estimate ({total_with_tools:,}) exceeds model limit ({self.max_context_length:,})!")

                # Debug: Log messages being sent to LLM to verify thinking content is removed
                logger.info(f"[LLM_CONTEXT_DEBUG] Sending {len(messages)} messages to LLM in iteration {iteration}")
                for idx, msg in enumerate(messages):
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")
                    content_preview = content[:200] if content else "(no content)"
                    has_think_tag = "<think>" in content.lower() or "</think>" in content.lower() if content else False
                    logger.info(f"  Message {idx}: role={role}, length={len(content) if content else 0}, has_think_tags={has_think_tag}")
                    if has_think_tag:
                        logger.warning(f"  ⚠️  THINKING CONTENT DETECTED IN MESSAGE {idx}!")
                        logger.warning(f"  Content preview: {content_preview}")

                # Call LLM with available tools using streaming mode
                # Streaming solves oauth-proxy timeout by sending response headers immediately
                # and keeps connection alive while streaming tokens to UI in real-time
                llm_start = time.time()
                try:
                    # Use streaming mode to avoid oauth-proxy timeout
                    # Build API call parameters
                    api_params = {
                        "model": self.llm_model,
                        "messages": messages,
                        "tools": self.mcp_tools,
                        "tool_choice": "auto",
                        "max_tokens": 2048,
                        "temperature": 0.1,
                        "top_p": 0.95,
                        "stream": True  # Enable streaming to keep connection alive and stream to UI
                    }

                    stream = await self.llm_client.chat.completions.create(**api_params)

                    # Stream response while handling thinking content
                    # NOTE: vLLM filters the FIRST <think> tag but allows subsequent ones and all </think> tags
                    # Strategy when reasoning enabled: Everything before first </think> is thinking, then parse normally
                    # Strategy when reasoning disabled: Stream all content as response
                    # NOTE: Tool calls come as <TOOLCALL> tags in text content, not in delta.tool_calls
                    accumulated_content = ""
                    first_close_tag_found = False if enable_reasoning else True  # Skip thinking logic if disabled
                    inside_think_tag = False
                    content_buffer = ""  # Buffer to handle tags split across chunks

                    async for chunk in stream:
                        delta = chunk.choices[0].delta

                        # Process content (accumulate in buffer to handle split tags)
                        if delta.content:
                            content_buffer += delta.content
                            logger.debug(f" Received chunk: {repr(delta.content[:100])}, buffer size: {len(content_buffer)}, first_close_tag_found={first_close_tag_found}, inside_think_tag={inside_think_tag}")

                            while content_buffer:
                                if enable_reasoning and not first_close_tag_found:
                                    # Reasoning enabled: streaming first thinking block (no opening tag from vLLM)
                                    close_idx = content_buffer.lower().find('</think>')
                                    if close_idx != -1:
                                        # Found first </think> - send thinking before it
                                        if content_buffer[:close_idx]:
                                            logger.debug(f" Sending thinking (before first close tag): {repr(content_buffer[:close_idx][:50])}")
                                            yield {
                                                "type": "llm_thinking",
                                                "content": content_buffer[:close_idx],
                                                "iteration": iteration
                                            }
                                        first_close_tag_found = True
                                        content_buffer = content_buffer[close_idx + 8:]  # Skip </think>
                                        logger.debug(f" Found first </think>, buffer after: {repr(content_buffer[:50])}")
                                    else:
                                        # No closing tag found yet - send all but last 8 chars (tag length)
                                        # Keep last 8 chars in buffer in case tag is being split
                                        if len(content_buffer) > 8:
                                            to_send = content_buffer[:-8]
                                            content_buffer = content_buffer[-8:]
                                            logger.debug(f" Sending thinking (no close tag yet): {repr(to_send[:50])}")
                                            yield {
                                                "type": "llm_thinking",
                                                "content": to_send,
                                                "iteration": iteration
                                            }
                                        break
                                elif inside_think_tag:
                                    # Inside a subsequent <think> block
                                    close_idx = content_buffer.lower().find('</think>')
                                    if close_idx != -1:
                                        # Found closing tag - send thinking before it
                                        if content_buffer[:close_idx]:
                                            logger.debug(f" Sending thinking (inside block): {repr(content_buffer[:close_idx][:50])}")
                                            yield {
                                                "type": "llm_thinking",
                                                "content": content_buffer[:close_idx],
                                                "iteration": iteration
                                            }
                                        inside_think_tag = False
                                        content_buffer = content_buffer[close_idx + 8:]
                                        logger.debug(f" Exited think block, buffer: {repr(content_buffer[:50])}")
                                    else:
                                        # No closing tag - send all but last 8 chars
                                        if len(content_buffer) > 8:
                                            to_send = content_buffer[:-8]
                                            content_buffer = content_buffer[-8:]
                                            logger.debug(f" Sending thinking (inside block, no close yet): {repr(to_send[:50])}")
                                            yield {
                                                "type": "llm_thinking",
                                                "content": to_send,
                                                "iteration": iteration
                                            }
                                        break
                                else:
                                    # Outside thinking blocks - check for tags or stream as response
                                    # Check for <TOOLCALL> tag first (don't stream tool calls)
                                    toolcall_start = content_buffer.lower().find('<toolcall>')
                                    if toolcall_start != -1:
                                        # Found <TOOLCALL> - stream content before it, then skip to </TOOLCALL>
                                        if content_buffer[:toolcall_start]:
                                            accumulated_content += content_buffer[:toolcall_start]
                                            logger.debug(f" Sending response (before <TOOLCALL>): {repr(content_buffer[:toolcall_start][:50])}")
                                            yield {
                                                "type": "llm_content_delta",
                                                "content": content_buffer[:toolcall_start],
                                                "iteration": iteration
                                            }
                                        # Find </TOOLCALL> and skip entire tool call block
                                        toolcall_end = content_buffer.lower().find('</toolcall>', toolcall_start)
                                        if toolcall_end != -1:
                                            # Skip entire <TOOLCALL>...</TOOLCALL> block (but keep in accumulated_content for parsing)
                                            toolcall_block = content_buffer[toolcall_start:toolcall_end + 11]
                                            accumulated_content += toolcall_block
                                            content_buffer = content_buffer[toolcall_end + 11:]
                                            logger.debug(f" Skipped TOOLCALL block, buffer after: {repr(content_buffer[:50])}")
                                        else:
                                            # </TOOLCALL> not found yet - keep last 11 chars in buffer
                                            if len(content_buffer) > 11:
                                                to_keep = content_buffer[toolcall_start:]
                                                accumulated_content += content_buffer[:toolcall_start]
                                                content_buffer = to_keep
                                            break
                                    else:
                                        # Check for <think> tag
                                        open_idx = content_buffer.lower().find('<think>') if enable_reasoning else -1
                                        if open_idx != -1:
                                            # Found opening tag - stream content before it as response (accumulate)
                                            if content_buffer[:open_idx]:
                                                accumulated_content += content_buffer[:open_idx]
                                                logger.debug(f" Sending response (before <think>): {repr(content_buffer[:open_idx][:50])}")
                                                yield {
                                                    "type": "llm_content_delta",
                                                    "content": content_buffer[:open_idx],
                                                    "iteration": iteration
                                                }
                                            content_buffer = content_buffer[open_idx + 7:]  # Skip <think>
                                            inside_think_tag = True
                                            logger.debug(f" Entering think block, buffer: {repr(content_buffer[:50])}")
                                        else:
                                            # No tag - send all but last 11 chars (in case <TOOLCALL> or <think> is being split)
                                            if len(content_buffer) > 11:
                                                to_send = content_buffer[:-11]
                                                content_buffer = content_buffer[-11:]
                                                accumulated_content += to_send
                                                logger.debug(f" Sending response (no tags): {repr(to_send[:50])}")
                                                yield {
                                                    "type": "llm_content_delta",
                                                    "content": to_send,
                                                    "iteration": iteration
                                                }
                                            break

                    # Flush any remaining buffer content at end of stream
                    if content_buffer:
                        logger.debug(f" Flushing remaining buffer ({len(content_buffer)} chars): {repr(content_buffer[:50])}")
                        if enable_reasoning and not first_close_tag_found:
                            # Still in thinking mode - send as thinking
                            yield {
                                "type": "llm_thinking",
                                "content": content_buffer,
                                "iteration": iteration
                            }
                        elif inside_think_tag:
                            # Inside think tag - send as thinking
                            yield {
                                "type": "llm_thinking",
                                "content": content_buffer,
                                "iteration": iteration
                            }
                        else:
                            # Outside thinking - send as response and accumulate
                            accumulated_content += content_buffer
                            yield {
                                "type": "llm_content_delta",
                                "content": content_buffer,
                                "iteration": iteration
                            }
                        content_buffer = ""

                    llm_elapsed = time.time() - llm_start
                    total_llm_time += llm_elapsed

                    # Create a message object from accumulated data
                    # Parse tool calls from accumulated content (vLLM doesn't populate delta.tool_calls during streaming)
                    logger.debug(f" End of stream - accumulated_content: {repr(accumulated_content[:200] if accumulated_content else None)}")
                    parsed_tool_calls = self._parse_tool_calls_from_text(accumulated_content) if accumulated_content else []
                    logger.debug(f" Parsed {len(parsed_tool_calls)} tool calls from text")

                    # Clean accumulated content to remove thinking and tool call tags
                    cleaned_content = self._clean_response_text(accumulated_content) if accumulated_content else None
                    logger.debug(f" After cleaning - cleaned_content: {repr(cleaned_content[:200] if cleaned_content else None)}")

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

                # Note: Thinking content is now streamed in real-time during the streaming loop above
                # No need to extract it again here

                # Parse tool calls from message
                tool_calls = message.tool_calls if message.tool_calls else []
                logger.debug(f" message.tool_calls: {tool_calls}")
                if not tool_calls and message.content:
                    tool_calls = self._parse_tool_calls_from_text(message.content)
                    logger.debug(f" Parsed tool_calls from text: {tool_calls}")

                # If no tool calls, we have the final answer
                if not tool_calls:
                    logger.debug(f" No tool calls found, treating as final answer")
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
                logger.debug(f" Executing {len(tool_calls)} tool calls")
                cleaned_content = self._clean_response_text(message.content) if message.content else ""

                logger.debug(f" Building tool_calls structure for messages array")
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
                    logger.debug(f" Tool calls structure built successfully")
                except Exception as e:
                    logger.debug(f" Error building tool_calls structure: {e}")
                    raise

                messages.append({
                    "role": "assistant",
                    "content": cleaned_content,
                    "tool_calls": tool_calls_for_message
                })

                logger.debug(f" Starting tool execution loop")
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

                    # Send tool completion event without result data
                    # (results may contain sensitive data that violates governance policy)
                    yield {
                        "type": "tool_result",
                        "tool_name": tool_name,
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


@app.post("/query/stream")
async def query_stream(request: QueryRequest):
    """
    Process user query with Server-Sent Events (SSE) for real-time progress updates.

    Streams events including:
    - iteration_start: When each iteration begins
    - llm_thinking: LLM's reasoning process
    - tool_call: When tools are executed
    - tool_result: Tool execution complete (timing only, no data for governance)
    - final_response: The complete answer
    - timing_summary: Performance breakdown
    - error: If something goes wrong
    """
    if not copilot:
        raise HTTPException(status_code=503, detail="Copilot not initialized")

    async def event_generator():
        """Generate SSE formatted events"""
        try:
            async for event in copilot.process_query_stream(
                request.query,
                request.conversation_id,
                request.enable_reasoning
            ):
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
    logger.info(f"Policy uploaded successfully - {len(governance_policy)} characters")
    logger.info(f"Policy preview: {governance_policy[:200]}...")

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

    logger.info("Policy deleted - new conversations will use default system prompt")
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
