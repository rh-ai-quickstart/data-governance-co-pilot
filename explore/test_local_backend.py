#!/usr/bin/env python3
"""Test local copilot backend with SSE streaming"""

import requests
import json
import sseclient  # pip install sseclient-py

def test_query_stream():
    """Test the /query/stream endpoint"""
    
    url = "http://localhost:8080/query/stream"
    
    payload = {
        "query": "List all schemas in the database",
        "conversation_id": None,  # or a UUID for conversation tracking
        "enable_reasoning": True
    }
    
    print(f"Sending query: {payload['query']}")
    print("=" * 70)
    
    # Make POST request with streaming
    response = requests.post(
        url,
        json=payload,
        stream=True,
        headers={"Accept": "text/event-stream"}
    )
    
    # Parse SSE events
    client = sseclient.SSEClient(response)
    
    for event in client.events():
        if event.data:
            try:
                data = json.loads(event.data)
                event_type = data.get("type", "unknown")
                
                # Handle different event types
                if event_type == "query_start":
                    print(f"\n🚀 Query started at {data.get('timestamp')}")
                
                elif event_type == "iteration_start":
                    print(f"\n🔄 Iteration {data.get('iteration')}/{data.get('max_iterations')}")
                
                elif event_type == "llm_thinking":
                    print(f"💭 {data.get('content')}", end="", flush=True)
                
                elif event_type == "llm_content_delta":
                    print(data.get("content"), end="", flush=True)
                
                elif event_type == "tool_call":
                    print(f"\n🔧 Tool: {data.get('tool_name')}")
                    print(f"   Args: {data.get('arguments')}")
                
                elif event_type == "tool_result":
                    print(f"   ✅ Completed in {data.get('mcp_time', 0):.2f}s")
                
                elif event_type == "final_response":
                    print(f"\n\n{'=' * 70}")
                    print("📋 FINAL RESPONSE:")
                    print(data.get("content"))
                
                elif event_type == "timing_summary":
                    print(f"\n{'=' * 70}")
                    print("⏱️  TIMING SUMMARY:")
                    print(f"   Total: {data.get('total_time', 0):.2f}s")
                    print(f"   LLM: {data.get('llm_time', 0):.2f}s")
                    print(f"   MCP: {data.get('mcp_time', 0):.2f}s")
                    print(f"   Iterations: {data.get('iterations')}")
                    print(f"   Tool calls: {data.get('tool_calls')}")
                    print(f"   Context usage: {data.get('context_usage_pct', 0):.1f}%")
                
                elif event_type == "error":
                    print(f"\n❌ ERROR: {data.get('message')}")
                    if "traceback" in data:
                        print(data.get("traceback"))
                
            except json.JSONDecodeError:
                print(f"Invalid JSON: {event.data}")

def test_health():
    """Test the /health endpoint"""
    response = requests.get("http://localhost:8080/health")
    print("Health Check:")
    print(json.dumps(response.json(), indent=2))

def test_tools():
    """Test the /tools endpoint"""
    response = requests.get("http://localhost:8080/tools")
    data = response.json()
    print(f"\nAvailable Tools ({data.get('count')}):")
    for tool in data.get('tools', []):
        print(f"  - {tool['function']['name']}: {tool['function']['description'][:60]}...")

if __name__ == "__main__":
    # Install: pip install requests sseclient-py
    
    print("Testing local copilot backend...\n")
    
    # Test health
    test_health()
    
    # Test tools
    test_tools()
    
    # Test query streaming
    print("\n" + "=" * 70)
    test_query_stream()
