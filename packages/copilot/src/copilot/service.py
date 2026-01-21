"""
Data Governance Copilot Service

FastAPI backend that orchestrates interactions between:
- Nemotron LLM (via OpenAI-compatible API)
- pg-airman-mcp server (PostgreSQL analysis tools)
"""
import json
import os
import re
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from openai import AsyncOpenAI
from pydantic import BaseModel


class QueryRequest(BaseModel):
    """User query request model"""
    query: str
    conversation_id: str | None = None


class QueryResponse(BaseModel):
    """Response model for queries"""
    response: str
    tool_calls: list[dict[str, Any]] | None = None
    conversation_id: str | None = None


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

        # MCP Configuration
        self.mcp_server_url = os.getenv(
            "PG_AIRMAN_MCP_SERVICE_PORT",
            "http://pg-airman-mcp-service:8000"
        ) + "/mcp"

        # Initialize OpenAI client for Nemotron
        self.llm_client = AsyncOpenAI(
            base_url=self.llm_base_url,
            api_key=self.llm_api_key
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
        print(f"[DEBUG] Content preview: {content[:200]}")

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
        print(f"[DEBUG] Cleaned preview: {content[:200]}")

        return content

    async def process_query(self, user_query: str) -> dict[str, Any]:
        """
        Process user query through LLM with MCP tool support.

        Implements agentic loop:
        1. Send query to LLM with available tools
        2. If LLM wants to use tools, execute them via MCP
        3. Send tool results back to LLM
        4. Repeat until LLM returns final answer
        """
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a data governance assistant with access to PostgreSQL "
                    "database analysis tools. Help users understand and optimize their "
                    "database performance, schema design, and query patterns. "
                    "When analyzing databases, use the available tools to provide "
                    "accurate, data-driven insights."
                )
            },
            {
                "role": "user",
                "content": user_query
            }
        ]

        tool_calls_made = []
        max_iterations = 10  # Prevent infinite loops
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            # Call LLM with available tools
            response = await self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=messages,
                tools=self.mcp_tools,
                tool_choice="auto"
            )

            message = response.choices[0].message

            # Parse tool calls from message (either structured or from text)
            tool_calls = message.tool_calls if message.tool_calls else []

            # If no structured tool calls, try parsing from text content
            if not tool_calls and message.content:
                tool_calls = self._parse_tool_calls_from_text(message.content)

            # If still no tool calls, we have the final answer
            if not tool_calls:
                return {
                    "response": self._clean_response_text(message.content),
                    "tool_calls": tool_calls_made
                }

            # Execute tool calls via MCP
            messages.append({
                "role": "assistant",
                "content": message.content,
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

                print(f"Executing MCP tool: {tool_name} with args: {tool_args}")

                # Execute tool via MCP
                tool_result = await self.mcp_session.call_tool(tool_name, tool_args)

                # Track tool calls for response
                tool_calls_made.append({
                    "tool": tool_name,
                    "arguments": tool_args,
                    "result": str(tool_result)
                })

                # Add tool result to conversation
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": str(tool_result)
                })

        # If we hit max iterations, return what we have
        return {
            "response": "Query processing exceeded maximum iterations. Please try a simpler query.",
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
        result = await copilot.process_query(request.query)
        return QueryResponse(
            response=result["response"],
            tool_calls=result.get("tool_calls"),
            conversation_id=request.conversation_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")


@app.get("/tools")
async def list_tools():
    """List available MCP tools"""
    if not copilot:
        raise HTTPException(status_code=503, detail="Copilot not initialized")

    return {
        "tools": copilot.mcp_tools,
        "count": len(copilot.mcp_tools)
    }
