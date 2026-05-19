#!/usr/bin/env python3
"""
Discover pg-airman-mcp server capabilities.

This script connects to the pg-airman-mcp server and retrieves:
- Server initialization info
- Available tools with descriptions
- Tool schemas (input parameters)
"""
import asyncio
import json
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def discover_mcp_capabilities(server_url: str = "http://localhost:8000/mcp"):
    """
    Connect to MCP server and discover its capabilities.

    Args:
        server_url: MCP server endpoint URL
    """
    print(f"🔌 Connecting to MCP server at {server_url}...")
    print("=" * 80)

    try:
        # Connect to MCP server
        async with streamablehttp_client(server_url) as (read, write, get_session_id):
            async with ClientSession(read, write) as session:
                # Initialize the session
                print("\n📡 Initializing MCP session...")
                init_result = await session.initialize()

                print(f"✅ Connected successfully!")
                print(f"\n{'=' * 80}")
                print("SERVER INFORMATION")
                print("=" * 80)
                print(f"Server Name: {init_result.serverInfo.name}")
                print(f"Server Version: {init_result.serverInfo.version}")
                print(f"Protocol Version: {init_result.protocolVersion}")

                # Get session ID if available
                try:
                    session_id = get_session_id()
                    print(f"Session ID: {session_id}")
                except Exception:
                    print("Session ID: Not available")

                # Discover capabilities
                print(f"\n{'=' * 80}")
                print("SERVER CAPABILITIES")
                print("=" * 80)

                if hasattr(init_result, 'capabilities'):
                    caps = init_result.capabilities
                    print(f"Capabilities: {caps}")
                else:
                    print("No capabilities info available")

                # List available tools
                print(f"\n{'=' * 80}")
                print("AVAILABLE TOOLS")
                print("=" * 80)

                tools_response = await session.list_tools()
                print(f"\nTotal Tools: {len(tools_response.tools)}\n")

                for i, tool in enumerate(tools_response.tools, 1):
                    print(f"{i}. {tool.name}")
                    print(f"   Description: {tool.description}")

                    # Show input schema
                    if hasattr(tool, 'inputSchema'):
                        schema = tool.inputSchema
                        print(f"   Input Schema:")
                        print(f"     Type: {schema.get('type', 'N/A')}")

                        if 'properties' in schema:
                            print(f"     Parameters:")
                            for param_name, param_info in schema['properties'].items():
                                param_type = param_info.get('type', 'unknown')
                                param_desc = param_info.get('description', 'No description')
                                required = param_name in schema.get('required', [])
                                req_marker = " [REQUIRED]" if required else " [OPTIONAL]"
                                print(f"       - {param_name} ({param_type}){req_marker}")
                                print(f"         {param_desc}")
                        else:
                            print(f"     No parameters")

                    print()  # Blank line between tools

                # Probe for prompts
                print(f"{'=' * 80}")
                print("PROMPTS")
                print("=" * 80)

                prompts_data = []
                try:
                    prompts_response = await session.list_prompts()
                    print(f"\nTotal Prompts: {len(prompts_response.prompts)}\n")

                    if prompts_response.prompts:
                        for i, prompt in enumerate(prompts_response.prompts, 1):
                            print(f"{i}. {prompt.name}")
                            print(f"   Description: {prompt.description if hasattr(prompt, 'description') else 'N/A'}")

                            # Show arguments if available
                            if hasattr(prompt, 'arguments'):
                                print(f"   Arguments:")
                                for arg in prompt.arguments:
                                    print(f"     - {arg.name}: {arg.description if hasattr(arg, 'description') else 'N/A'}")
                            print()

                            prompts_data.append({
                                "name": prompt.name,
                                "description": prompt.description if hasattr(prompt, 'description') else None,
                                "arguments": [
                                    {
                                        "name": arg.name,
                                        "description": arg.description if hasattr(arg, 'description') else None,
                                        "required": arg.required if hasattr(arg, 'required') else False
                                    }
                                    for arg in prompt.arguments
                                ] if hasattr(prompt, 'arguments') else []
                            })
                    else:
                        print("No prompts available.\n")

                except Exception as e:
                    print(f"❌ Error querying prompts: {e}\n")

                # Probe for resources
                print(f"{'=' * 80}")
                print("RESOURCES")
                print("=" * 80)

                resources_data = []
                try:
                    resources_response = await session.list_resources()
                    print(f"\nTotal Resources: {len(resources_response.resources)}\n")

                    if resources_response.resources:
                        for i, resource in enumerate(resources_response.resources, 1):
                            print(f"{i}. {resource.uri}")
                            print(f"   Name: {resource.name if hasattr(resource, 'name') else 'N/A'}")
                            print(f"   Description: {resource.description if hasattr(resource, 'description') else 'N/A'}")
                            print(f"   MIME Type: {resource.mimeType if hasattr(resource, 'mimeType') else 'N/A'}")
                            print()

                            resources_data.append({
                                "uri": resource.uri,
                                "name": resource.name if hasattr(resource, 'name') else None,
                                "description": resource.description if hasattr(resource, 'description') else None,
                                "mime_type": resource.mimeType if hasattr(resource, 'mimeType') else None
                            })
                    else:
                        print("No resources available.\n")

                except Exception as e:
                    print(f"❌ Error querying resources: {e}\n")

                # Save detailed schema to JSON file
                tools_data = {
                    "server_info": {
                        "name": init_result.serverInfo.name,
                        "version": init_result.serverInfo.version,
                        "protocol_version": init_result.protocolVersion
                    },
                    "capabilities": {
                        "tools": {
                            "supported": True,
                            "list_changed": False
                        },
                        "prompts": {
                            "supported": len(prompts_data) > 0,
                            "list_changed": False,
                            "count": len(prompts_data)
                        },
                        "resources": {
                            "supported": len(resources_data) > 0,
                            "list_changed": False,
                            "subscribe": False,
                            "count": len(resources_data)
                        }
                    },
                    "tools": [
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "input_schema": tool.inputSchema if hasattr(tool, 'inputSchema') else None
                        }
                        for tool in tools_response.tools
                    ],
                    "prompts": prompts_data,
                    "resources": resources_data
                }

                output_file = "mcp_capabilities.json"
                with open(output_file, 'w') as f:
                    json.dump(tools_data, f, indent=2)

                print(f"{'=' * 80}")
                print(f"✅ Detailed capabilities saved to: {output_file}")
                print(f"{'=' * 80}\n")

    except Exception as e:
        print(f"\n❌ Error connecting to MCP server: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Run the discovery
    asyncio.run(discover_mcp_capabilities())
