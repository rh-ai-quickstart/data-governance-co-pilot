#!/usr/bin/env python3
"""
Test script to call explain_query tool directly on MCP server using official MCP SDK.
Assumes MCP server is port-forwarded to localhost:8000
"""

import asyncio
import json
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async def test_explain_query():
    """Test explain_query tool using official MCP SDK"""

    mcp_server_url = "http://localhost:8000/mcp"

    print(f"Connecting to MCP server at {mcp_server_url}...")

    # Use the same client that our copilot backend uses
    async with streamablehttp_client(mcp_server_url) as (read, write, _):
        async with ClientSession(read, write) as session:
            print("✅ Connected to MCP server\n")

            # Initialize the session
            print("Initializing session...")
            await session.initialize()
            print("✅ Session initialized\n")

            # List tools
            print("Listing tools...")
            tools_result = await session.list_tools()
            tool_names = [tool.name for tool in tools_result.tools]
            print(f"Available tools ({len(tool_names)}): {tool_names}\n")

            # Call explain_query tool
            print("Calling explain_query tool...")
            print("Arguments:")
            args = {
                "sql": "SELECT * FROM public.v_rpt_customer_ltv_certified LIMIT 10;",
                "analyze": True,
                "hypothetical_indexes": []
            }
            print(json.dumps(args, indent=2))
            print()

            result = await session.call_tool("explain_query", arguments=args)

            # Pretty print the response
            print("\n" + "="*80)
            print("RAW TOOL RESULT:")
            print("="*80)

            # MCP tool result has content attribute
            if hasattr(result, 'content') and result.content:
                for idx, content_item in enumerate(result.content):
                    print(f"\nContent item {idx + 1}:")
                    print(f"  Type: {content_item.type}")

                    if content_item.type == "text":
                        text = content_item.text
                        print(f"  Text length: {len(text)} characters")
                        print(f"\n  First 1000 chars:")
                        print(f"  {text[:1000]}")

                        # Try to parse as JSON
                        if text.strip().startswith('[') or text.strip().startswith('{'):
                            try:
                                parsed = json.loads(text)
                                print("\n  ✅ Content is valid JSON")

                                # Check if it's a query plan
                                if isinstance(parsed, list) and len(parsed) > 0:
                                    plan = parsed[0]
                                    print("\n  📊 Query Plan Metrics:")
                                    if "Execution Time" in plan:
                                        print(f"     ⏱️  Execution Time: {plan.get('Execution Time')} ms")
                                    if "Planning Time" in plan:
                                        print(f"     📋 Planning Time: {plan.get('Planning Time')} ms")
                                    if "Plan" in plan:
                                        node = plan['Plan']
                                        print(f"     🔍 Node Type: {node.get('Node Type')}")
                                        print(f"     💰 Total Cost: {node.get('Total Cost')}")
                                        print(f"     📈 Estimated Rows: {node.get('Plan Rows')}")
                                        print(f"     ✅ Actual Rows: {node.get('Actual Rows')}")

                                        print("\n  ✅✅✅ SUCCESS: Query plan returned successfully!")
                                        print("  The explain_query tool is working correctly.")
                                        print("  The LLM is likely misinterpreting this JSON as an error.")
                                elif isinstance(parsed, dict) and "error" in str(parsed).lower():
                                    print("\n  ❌ Response contains error information:")
                                    print(f"     {json.dumps(parsed, indent=6)}")

                            except json.JSONDecodeError as e:
                                print(f"\n  ❌ Content is NOT valid JSON: {e}")
                                print("  This is likely a plain text error message:")
                                print(f"  {text}")
            else:
                print("No content in result")
                print(f"Result attributes: {dir(result)}")

            print("="*80 + "\n")

if __name__ == "__main__":
    print("Testing explain_query tool on MCP server using official MCP SDK")
    print("Assuming MCP server is port-forwarded to localhost:8000\n")
    asyncio.run(test_explain_query())
