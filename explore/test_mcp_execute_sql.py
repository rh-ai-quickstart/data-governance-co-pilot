#!/usr/bin/env python3
"""
Test MCP execute_sql tool to see raw response format.

Prerequisites:
- Port-forward to MCP server: oc port-forward svc/pg-airman-mcp-service 8000:8000
- Virtual environment activated with mcp library installed
"""

import asyncio
import json
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def test_execute_sql():
    """Call execute_sql tool and print raw MCP response"""

    mcp_url = "http://localhost:8000/mcp"

    print(f"Connecting to MCP server at {mcp_url}...")
    print("=" * 70)

    try:
        # Connect to MCP server
        async with streamablehttp_client(mcp_url) as (read, write, get_session_id):
            async with ClientSession(read, write) as session:
                # Initialize session
                await session.initialize()
                print("✅ Connected to MCP server\n")

                # Call execute_sql tool
                query = "select * from public.fact_orders limit 2;"
                print(f"Executing SQL query:")
                print(f"  {query}\n")

                result = await session.call_tool(
                    "execute_sql",
                    {"sql": query}
                )

                print("=" * 70)
                print("RAW MCP RESPONSE:")
                print("=" * 70)

                # Print the full result object
                print(f"Result type: {type(result)}")
                print(f"Result attributes: {dir(result)}\n")

                # Print as dict if possible
                if hasattr(result, '__dict__'):
                    print("Result as dict:")
                    print(json.dumps(result.__dict__, indent=2, default=str))
                else:
                    print("Result:")
                    print(result)

                print("\n" + "=" * 70)
                print("CONTENT FIELD:")
                print("=" * 70)

                # Print the content field specifically
                if hasattr(result, 'content'):
                    print(f"Content type: {type(result.content)}")
                    print(f"Content length: {len(result.content)}\n")

                    for i, item in enumerate(result.content):
                        print(f"Content item {i}:")
                        print(f"  Type: {type(item)}")
                        if hasattr(item, '__dict__'):
                            print(f"  Dict: {json.dumps(item.__dict__, indent=4, default=str)}")
                        else:
                            print(f"  Value: {item}")
                        print()

                print("=" * 70)
                print("PARSED DATA (if JSON in text field):")
                print("=" * 70)

                # Try to parse JSON from text content
                if hasattr(result, 'content') and len(result.content) > 0:
                    first_item = result.content[0]
                    if hasattr(first_item, 'text'):
                        try:
                            parsed_data = json.loads(first_item.text)
                            print(json.dumps(parsed_data, indent=2))
                        except json.JSONDecodeError:
                            print("Content is not JSON, raw text:")
                            print(first_item.text)

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\nMCP execute_sql Tool Test")
    print("=" * 70)
    print("This script calls the execute_sql tool and prints the raw response\n")

    asyncio.run(test_execute_sql())
