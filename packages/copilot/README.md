# Data Governance Copilot

MCP (Model Context Protocol) client for interacting with PostgreSQL databases via the pg-airman-mcp server.

## Overview

This package is an MCP client that connects to the `pg-airman-mcp` server to perform database operations, analysis, and governance tasks.

## Architecture

```
┌─────────────────┐        SSE/HTTP         ┌──────────────────┐
│   Copilot       │ ◄─────────────────────► │  pg-airman-mcp   │
│  (MCP Client)   │                         │   (MCP Server)   │
└─────────────────┘                         └────────┬─────────┘
                                                     │
                                            ┌────────▼─────────┐
                                            │   PostgreSQL     │
                                            └──────────────────┘
```

## Prerequisites

- Python 3.12+
- pg-airman-mcp server deployed (via `helm/pg-airman-mcp` chart)
- Network access to the MCP server

## Installation

```bash
# From the repository root
uv sync

# Or install the package directly
cd packages/copilot
uv pip install -e .
```

## Configuration

The copilot uses environment variables for configuration:

| Variable | Description | Default |
|----------|-------------|---------|
| `PG_AIRMAN_MCP_SERVICE_PORT` | URL of the pg-airman-mcp server | `http://pg-airman-mcp-service:8000` |

Create a `.env` file based on `.env.example`:

```bash
cp .env.example .env
# Edit .env with your configuration
```

## Usage

### Command Line

```bash
# Run the copilot
copilot

# Or via Python module
python -m copilot
```

### Programmatic Usage

```python
import asyncio
from copilot.copilot import connect_to_pg_airman

async def main():
    async with sse_client("http://pg-airman-mcp-service:8000/sse") as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # List schemas
            schemas = await session.call_tool("list_schemas", {})
            print(schemas)

            # Analyze database health
            health = await session.call_tool("analyze_db_health", {})
            print(health)

asyncio.run(main())
```

## Available MCP Tools

The copilot can access these tools from the pg-airman-mcp server:

- `list_schemas` - Enumerate database schemas
- `list_objects` - Display tables, views, sequences
- `get_object_details` - Retrieve column info, constraints, indexes
- `execute_sql` - Run SQL queries
- `explain_query` - Generate execution plans
- `get_top_queries` - Identify slow queries
- `analyze_workload_indexes` - Recommend indexes for workload
- `analyze_query_indexes` - Suggest indexes for specific queries
- `analyze_db_health` - Check database health metrics
- `add_comment_to_object` - Document database objects

## Transport: Streamable HTTP

This client uses **streamable HTTP** transport to connect to pg-airman-mcp:

### Streamable HTTP Benefits
- ✅ Simple request-response pattern
- ✅ No persistent connections needed
- ✅ Works through strict proxies and load balancers
- ✅ Standard HTTP-based communication
- ✅ Easy to debug with standard HTTP tools

### Alternative: SSE (Server-Sent Events)
- Long-lived connections for streaming
- Better for real-time updates
- More complex infrastructure requirements

To use SSE instead, update the helm chart's `values.yaml`:

```yaml
mcp:
  transport: sse
```

And update the client to use `sse_client` from `mcp.client.sse`.

## Deployment

### Kubernetes/OpenShift

Deploy as a pod alongside the pg-airman-mcp service:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: copilot
spec:
  template:
    spec:
      containers:
      - name: copilot
        image: copilot:latest
        env:
        - name: PG_AIRMAN_MCP_SERVICE_PORT
          value: "http://pg-airman-mcp-service:8000"
```

### Local Development

For local testing against a remote MCP server:

```bash
# Port forward the MCP service
kubectl port-forward svc/pg-airman-mcp-service 8000:8000

# Update .env
echo "PG_AIRMAN_MCP_SERVICE_PORT=http://localhost:8000" > .env

# Run copilot
copilot
```

## Development

### Running Tests

```bash
# Run tests
pytest

# With coverage
pytest --cov=copilot
```

### Project Structure

```
packages/copilot/
├── src/copilot/
│   ├── __init__.py
│   ├── __main__.py      # Entry point
│   └── copilot.py       # Main client logic
├── pyproject.toml       # Package configuration
├── README.md            # This file
└── .env.example         # Example configuration
```

## Troubleshooting

### Connection Refused

```
Error: Connection refused to http://pg-airman-mcp-service:8000/sse
```

**Solution**: Ensure the pg-airman-mcp server is deployed and running:

```bash
kubectl get pods -l app.kubernetes.io/name=pg-airman-mcp
kubectl get svc pg-airman-mcp-service
```

### MCP Server Not Starting

Check the pg-airman-mcp logs:

```bash
kubectl logs -l app.kubernetes.io/name=pg-airman-mcp -f
```

Verify the server is running with SSE transport:

```bash
# Should see: --transport=sse in the args
kubectl describe pod -l app.kubernetes.io/name=pg-airman-mcp
```

## Resources

- [pg-airman-mcp Documentation](https://github.com/EnterpriseDB/pg-airman-mcp)
- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
