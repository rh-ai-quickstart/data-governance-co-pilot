# MCP Access Mode Verification Guide

## Overview

This guide verifies that the pg-airman-mcp server correctly enforces access mode restrictions when executing SQL queries.

**Configured Access Mode (from values.yaml):**
```yaml
mcp:
  accessMode: restricted  # Read-only operations, query timeout limits
```

In **restricted** mode:
- ✅ SELECT queries are allowed
- ✅ EXPLAIN queries are allowed
- ✅ Schema inspection tools work
- ❌ INSERT/UPDATE/DELETE/TRUNCATE queries are **denied**
- ❌ DDL operations (CREATE, ALTER, DROP) are **denied**
- ⏱️ Query timeout limits apply

In **unrestricted** mode (development only):
- ✅ All SQL operations allowed (dangerous in production!)

---

## Prerequisites

**Tools Required:**
- `oc` CLI (OpenShift command-line tool)
- `python3` with `mcp` library installed (available in copilot-backend container)
- Access to the namespace where pg-airman-mcp is deployed

**Network Access:**
- Port-forwarding to pg-airman-mcp service (no public route by default)

---

## Setup: Port Forwarding

The pg-airman-mcp service is internal (ClusterIP) with no public route. You need to port-forward to access it:

### Option 1: Port Forward from Local Machine

```bash
# Get the service name
oc get svc -n <namespace> | grep pg-airman-mcp

# Port forward (runs in foreground)
oc port-forward -n <namespace> svc/pg-airman-mcp-service 8000:8000
```

**Keep this terminal open** - the port forward will run until you press Ctrl+C.

Open a new terminal for running tests.

### Option 2: Execute Tests from copilot-backend Pod

Alternatively, run tests directly from the copilot-backend pod (which can already reach the MCP service):

```bash
# Get copilot-backend pod name
POD=$(oc get pods -n <namespace> -l app=copilot-backend -o jsonpath='{.items[0].metadata.name}')

# Open shell in the pod
oc exec -it $POD -n <namespace> -- bash
```

From inside the pod, you can access the MCP service at `http://pg-airman-mcp-service:8000/mcp`.

---

## Test 1: Verify Access Mode Configuration

### Test 1.1: Check Deployment Configuration

```bash
# Get pg-airman-mcp pod
POD=$(oc get pods -n <namespace> -l app.kubernetes.io/name=pg-airman-mcp -o jsonpath='{.items[0].metadata.name}')

# Check the access-mode argument
oc get pod $POD -n <namespace> -o jsonpath='{.spec.containers[0].args}' | jq .
```

**Expected Output:**
```json
[
  "pg-airman-mcp",
  "--transport=streamable-http",
  "--access-mode=restricted",
  "--streamable-http-port=8000"
]
```

**✅ PASS:** Access mode is set to `restricted`.

**❌ FAIL:** Access mode is `unrestricted` or missing.

---

### Test 1.2: Check MCP Server Logs

```bash
# View startup logs to confirm access mode
oc logs $POD -n <namespace> | grep -i "access\|mode\|restricted"
```

**Expected Output:**
```
INFO: Access mode: restricted
INFO: Starting MCP server with streamable-http transport on port 8000
```

---

## Test 2: Read Query (Should Succeed)

**Purpose:** Verify that SELECT queries work in restricted mode.

### Test 2.1: Simple SELECT Query

Create a test script `test_read.py`:

```python
#!/usr/bin/env python3
"""Test MCP server with a read query (should succeed)"""

import asyncio
import json
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async def test_read_query():
    # Use localhost:8000 if port-forwarding, or service URL if running inside cluster
    mcp_url = "http://localhost:8000/mcp"
    # mcp_url = "http://pg-airman-mcp-service:8000/mcp"  # Use this inside cluster
    
    print(f"Connecting to MCP server at {mcp_url}...")
    
    try:
        async with streamablehttp_client(mcp_url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                print("✅ Connected to MCP server")
                
                # List available tools
                tools_response = await session.list_tools()
                print(f"✅ Available tools: {len(tools_response.tools)}")
                
                # Execute a simple SELECT query
                print("\n🔍 Attempting SELECT query...")
                result = await session.call_tool(
                    "execute_sql",
                    {"query": "SELECT 1 AS test_value"}
                )
                
                print(f"✅ SELECT query succeeded!")
                print(f"Result: {result.content}")
                
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_read_query())
```

**Run the test:**

```bash
# From local machine (with port-forward active)
python3 test_read.py

# OR from copilot-backend pod
oc exec $POD -n <namespace> -- python3 /tmp/test_read.py
```

**Expected Output:**
```
Connecting to MCP server at http://localhost:8000/mcp...
✅ Connected to MCP server
✅ Available tools: 11
🔍 Attempting SELECT query...
✅ SELECT query succeeded!
Result: [{"type": "text", "text": "..."}]
```

**✅ PASS:** SELECT query completes successfully.

**❌ FAIL:** Connection fails, query is denied, or server returns error.

---

## Test 3: DELETE Query (Should Be Denied)

**Purpose:** Verify that DELETE queries are blocked in restricted mode.

### Test 3.1: Attempt DELETE Query

Create a test script `test_delete.py`:

```python
#!/usr/bin/env python3
"""Test MCP server with a DELETE query (should be denied in restricted mode)"""

import asyncio
import json
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async def test_delete_query():
    # Use localhost:8000 if port-forwarding, or service URL if running inside cluster
    mcp_url = "http://localhost:8000/mcp"
    # mcp_url = "http://pg-airman-mcp-service:8000/mcp"  # Use this inside cluster
    
    print(f"Connecting to MCP server at {mcp_url}...")
    
    try:
        async with streamablehttp_client(mcp_url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                print("✅ Connected to MCP server")
                
                # Attempt a DELETE query (should be denied)
                print("\n🚫 Attempting DELETE query (expecting denial)...")
                result = await session.call_tool(
                    "execute_sql",
                    {"query": "DELETE FROM pg_class WHERE false"}
                )
                
                # If we get here, the query was NOT blocked
                print(f"❌ FAIL: DELETE query was allowed in restricted mode!")
                print(f"Result: {result.content}")
                
    except Exception as e:
        # Expected: MCP server should return an error
        error_message = str(e)
        if any(keyword in error_message.lower() for keyword in [
            "denied", "not allowed", "restricted", "read-only", 
            "permission", "access mode", "delete"
        ]):
            print(f"✅ PASS: DELETE query was correctly denied!")
            print(f"Error message: {error_message}")
        else:
            print(f"⚠️  DELETE query failed, but with unexpected error:")
            print(f"Error: {error_message}")

if __name__ == "__main__":
    asyncio.run(test_delete_query())
```

**Run the test:**

```bash
# From local machine (with port-forward active)
python3 test_delete.py

# OR from copilot-backend pod
oc exec $POD -n <namespace> -- python3 /tmp/test_delete.py
```

**Expected Output:**
```
Connecting to MCP server at http://localhost:8000/mcp...
✅ Connected to MCP server
🚫 Attempting DELETE query (expecting denial)...
✅ PASS: DELETE query was correctly denied!
Error message: Query denied in restricted mode: DELETE not allowed
```

**✅ PASS:** DELETE query is denied with appropriate error message.

**❌ FAIL:** DELETE query succeeds (access mode not enforced).

---

## Test 4: INSERT Query (Should Be Denied)

**Purpose:** Verify that INSERT queries are blocked in restricted mode.

### Test 4.1: Attempt INSERT Query

```python
#!/usr/bin/env python3
"""Test MCP server with an INSERT query (should be denied in restricted mode)"""

import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async def test_insert_query():
    mcp_url = "http://localhost:8000/mcp"
    # mcp_url = "http://pg-airman-mcp-service:8000/mcp"  # Use this inside cluster
    
    print(f"Connecting to MCP server at {mcp_url}...")
    
    try:
        async with streamablehttp_client(mcp_url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                print("✅ Connected to MCP server")
                
                print("\n🚫 Attempting INSERT query (expecting denial)...")
                result = await session.call_tool(
                    "execute_sql",
                    {"query": "INSERT INTO pg_class DEFAULT VALUES"}
                )
                
                print(f"❌ FAIL: INSERT query was allowed in restricted mode!")
                print(f"Result: {result.content}")
                
    except Exception as e:
        error_message = str(e)
        if any(keyword in error_message.lower() for keyword in [
            "denied", "not allowed", "restricted", "read-only", 
            "permission", "access mode", "insert"
        ]):
            print(f"✅ PASS: INSERT query was correctly denied!")
            print(f"Error message: {error_message}")
        else:
            print(f"⚠️  INSERT query failed, but with unexpected error:")
            print(f"Error: {error_message}")

if __name__ == "__main__":
    asyncio.run(test_insert_query())
```

**✅ PASS:** INSERT query is denied.

**❌ FAIL:** INSERT query succeeds.

---

## Test 5: DDL Query (Should Be Denied)

**Purpose:** Verify that DDL operations (CREATE, ALTER, DROP) are blocked in restricted mode.

### Test 5.1: Attempt CREATE TABLE Query

```python
#!/usr/bin/env python3
"""Test MCP server with DDL query (should be denied in restricted mode)"""

import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async def test_ddl_query():
    mcp_url = "http://localhost:8000/mcp"
    # mcp_url = "http://pg-airman-mcp-service:8000/mcp"  # Use this inside cluster
    
    print(f"Connecting to MCP server at {mcp_url}...")
    
    try:
        async with streamablehttp_client(mcp_url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                print("✅ Connected to MCP server")
                
                print("\n🚫 Attempting CREATE TABLE query (expecting denial)...")
                result = await session.call_tool(
                    "execute_sql",
                    {"query": "CREATE TEMP TABLE test_table (id INT)"}
                )
                
                print(f"❌ FAIL: CREATE TABLE query was allowed in restricted mode!")
                print(f"Result: {result.content}")
                
    except Exception as e:
        error_message = str(e)
        if any(keyword in error_message.lower() for keyword in [
            "denied", "not allowed", "restricted", "read-only", 
            "permission", "access mode", "create"
        ]):
            print(f"✅ PASS: CREATE TABLE query was correctly denied!")
            print(f"Error message: {error_message}")
        else:
            print(f"⚠️  CREATE TABLE query failed, but with unexpected error:")
            print(f"Error: {error_message}")

if __name__ == "__main__":
    asyncio.run(test_ddl_query())
```

**✅ PASS:** DDL query is denied.

**❌ FAIL:** DDL query succeeds.

---

## Test 6: Alternative - cURL Test (Raw HTTP)

If you prefer to test without Python, you can use raw MCP JSON-RPC calls via cURL:

**Note:** MCP uses JSON-RPC 2.0 protocol over HTTP. The exact request format depends on the MCP server implementation.

```bash
# Initialize session (get capabilities)
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {
        "name": "test-client",
        "version": "1.0.0"
      }
    },
    "id": 1
  }'

# Call execute_sql tool with DELETE query
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "execute_sql",
      "arguments": {
        "query": "DELETE FROM pg_class WHERE false"
      }
    },
    "id": 2
  }'
```

**Note:** The exact JSON-RPC format may vary. Check MCP server logs for details if cURL tests fail.

---

## Test 7: All-in-One Test Script

Comprehensive test script that runs all scenarios:

```python
#!/usr/bin/env python3
"""Comprehensive MCP access mode verification"""

import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

# Test queries
TESTS = [
    {
        "name": "SELECT (should succeed)",
        "query": "SELECT 1 AS test",
        "should_succeed": True
    },
    {
        "name": "DELETE (should be denied)",
        "query": "DELETE FROM pg_class WHERE false",
        "should_succeed": False
    },
    {
        "name": "INSERT (should be denied)",
        "query": "INSERT INTO pg_class DEFAULT VALUES",
        "should_succeed": False
    },
    {
        "name": "UPDATE (should be denied)",
        "query": "UPDATE pg_class SET relname = relname WHERE false",
        "should_succeed": False
    },
    {
        "name": "CREATE TABLE (should be denied)",
        "query": "CREATE TEMP TABLE test_access_mode (id INT)",
        "should_succeed": False
    },
    {
        "name": "DROP TABLE (should be denied)",
        "query": "DROP TABLE IF EXISTS nonexistent_table",
        "should_succeed": False
    },
    {
        "name": "TRUNCATE (should be denied)",
        "query": "TRUNCATE pg_class",  # Would fail even if allowed
        "should_succeed": False
    }
]

async def run_comprehensive_test():
    mcp_url = "http://localhost:8000/mcp"
    # mcp_url = "http://pg-airman-mcp-service:8000/mcp"  # Inside cluster
    
    print("=" * 70)
    print("MCP Access Mode Verification - Comprehensive Test")
    print("=" * 70)
    print(f"\nConnecting to: {mcp_url}")
    
    results = {
        "passed": 0,
        "failed": 0,
        "total": len(TESTS)
    }
    
    try:
        async with streamablehttp_client(mcp_url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                print("✅ Connected to MCP server\n")
                
                # Get access mode from server (if available)
                tools = await session.list_tools()
                print(f"Available tools: {len(tools.tools)}\n")
                
                # Run each test
                for i, test in enumerate(TESTS, 1):
                    print(f"Test {i}/{len(TESTS)}: {test['name']}")
                    print(f"  Query: {test['query'][:60]}...")
                    
                    try:
                        result = await session.call_tool(
                            "execute_sql",
                            {"query": test["query"]}
                        )
                        
                        # Query succeeded
                        if test["should_succeed"]:
                            print(f"  ✅ PASS - Query succeeded as expected")
                            results["passed"] += 1
                        else:
                            print(f"  ❌ FAIL - Query succeeded but should have been denied!")
                            results["failed"] += 1
                            
                    except Exception as e:
                        # Query failed
                        error_msg = str(e)
                        
                        if not test["should_succeed"]:
                            # Expected failure
                            if any(kw in error_msg.lower() for kw in [
                                "denied", "not allowed", "restricted", 
                                "read-only", "permission", "access mode"
                            ]):
                                print(f"  ✅ PASS - Query correctly denied")
                                results["passed"] += 1
                            else:
                                print(f"  ⚠️  Query failed with unexpected error:")
                                print(f"     {error_msg[:100]}")
                                results["failed"] += 1
                        else:
                            print(f"  ❌ FAIL - Query failed but should have succeeded!")
                            print(f"     Error: {error_msg[:100]}")
                            results["failed"] += 1
                    
                    print()
                
                # Summary
                print("=" * 70)
                print("SUMMARY")
                print("=" * 70)
                print(f"Total Tests: {results['total']}")
                print(f"Passed: {results['passed']}")
                print(f"Failed: {results['failed']}")
                
                if results["failed"] == 0:
                    print("\n✅ ALL TESTS PASSED - Access mode restrictions working correctly!")
                else:
                    print(f"\n❌ {results['failed']} TESTS FAILED - Access mode may not be enforced!")
                
    except Exception as e:
        print(f"\n❌ Connection failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_comprehensive_test())
```

**Save this as `test_access_mode_comprehensive.py` and run:**

```bash
# From local machine (with port-forward)
python3 test_access_mode_comprehensive.py

# OR copy to copilot-backend pod and run
oc cp test_access_mode_comprehensive.py $POD:/tmp/ -n <namespace>
oc exec $POD -n <namespace> -- python3 /tmp/test_access_mode_comprehensive.py
```

**Expected Output:**
```
======================================================================
MCP Access Mode Verification - Comprehensive Test
======================================================================

Connecting to: http://localhost:8000/mcp
✅ Connected to MCP server

Available tools: 11

Test 1/7: SELECT (should succeed)
  Query: SELECT 1 AS test...
  ✅ PASS - Query succeeded as expected

Test 2/7: DELETE (should be denied)
  Query: DELETE FROM pg_class WHERE false...
  ✅ PASS - Query correctly denied

...

======================================================================
SUMMARY
======================================================================
Total Tests: 7
Passed: 7
Failed: 0

✅ ALL TESTS PASSED - Access mode restrictions working correctly!
```

---

## Summary Checklist

- [ ] **Configuration:** Access mode set to `restricted` in deployment (Test 1.1)
- [ ] **Read Access:** SELECT queries work (Test 2)
- [ ] **Write Denial:** DELETE queries blocked (Test 3)
- [ ] **Write Denial:** INSERT queries blocked (Test 4)
- [ ] **DDL Denial:** CREATE/ALTER/DROP queries blocked (Test 5)
- [ ] **Comprehensive:** All access mode tests pass (Test 7)

---

## Troubleshooting

### Port Forward Fails

**Symptom:** `error: unable to forward port because pod is not running`

**Solution:**
```bash
# Check pod status
oc get pods -n <namespace> -l app.kubernetes.io/name=pg-airman-mcp

# View logs if pod is crashing
oc logs -n <namespace> -l app.kubernetes.io/name=pg-airman-mcp
```

---

### MCP Connection Fails

**Symptom:** `Connection refused` or `404 Not Found`

**Solution:**
```bash
# Verify service exists
oc get svc pg-airman-mcp-service -n <namespace>

# Check service endpoints
oc get endpoints pg-airman-mcp-service -n <namespace>

# Verify MCP endpoint path is correct (should be /mcp)
oc logs $POD -n <namespace> | grep -i "listening\|started\|port"
```

---

### Access Mode Not Enforced

**Symptom:** Write queries succeed in restricted mode.

**Possible Causes:**
1. Deployment not using updated values.yaml
2. Pod running with wrong arguments
3. pg-airman-mcp version doesn't support access mode

**Check:**
```bash
# Verify deployment args
oc get pod $POD -n <namespace> -o yaml | grep -A 10 args

# Check pg-airman-mcp version
oc get pod $POD -n <namespace> -o jsonpath='{.spec.containers[0].image}'

# Redeploy with correct values
make install
```

---

### Python MCP Library Not Available

**Symptom:** `ModuleNotFoundError: No module named 'mcp'`

**Solution:**
```bash
# Install MCP library
pip install mcp

# OR run tests from copilot-backend pod (has MCP library installed)
oc exec -it $POD -n <namespace> -- bash
python3 /tmp/test_script.py
```

---

## Additional Resources

- [pg-airman-mcp GitHub](https://github.com/EnterpriseDB/pg-airman-mcp)
- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
