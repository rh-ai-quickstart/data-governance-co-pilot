import asyncio
import os
from typing import Any

from mcp import ClientSession
# streamablehttp_client is the official MCP client for streamable-http transport
# (not deprecated - naming follows MCP SDK conventions)
from mcp.client.streamable_http import streamablehttp_client


async def connect_to_pg_airman():
    """
    Connect to the pg-airman-mcp server via streamable-http transport.

    The MCP server should be deployed via the helm/pg-airman-mcp chart
    and accessible at the service endpoint.
    """
    # Get MCP server URL from environment variable or use default
    # Note: pg-airman-mcp serves MCP at the /mcp endpoint
    mcp_server_url = os.getenv(
        "PG_AIRMAN_MCP_SERVICE_PORT",
        "http://pg-airman-mcp-service:8000"
    )

    mcp_server_url += "/mcp"

    print(f"Connecting to pg-airman-mcp at {mcp_server_url}...")

    # Connect to the MCP server via streamable-http
    # streamablehttp_client returns (read, write, get_session_id)
    async with streamablehttp_client(mcp_server_url) as (read, write, get_session_id):
        async with ClientSession(read, write) as session:
            # Initialize the session
            await session.initialize()
            print("Connected to pg-airman-mcp server!")

            # List available tools
            tools = await session.list_tools()
            print(f"\nAvailable MCP tools ({len(tools.tools)}):")
            for tool in tools.tools:
                print(f"  - {tool.name}: {tool.description}")

            # Example: List database schemas
            print("\n--- Listing database schemas ---")
            result = await session.call_tool("list_schemas", {})
            print(result)

            # Example: Get database health
            print("\n--- Checking database health ---")
            health = await session.call_tool("analyze_db_health", {})
            print(health)

            return session


def start():
    """Entry point for the copilot application."""
    print("Starting Data Governance Copilot...")

    # Run the async connection
    asyncio.run(connect_to_pg_airman())

