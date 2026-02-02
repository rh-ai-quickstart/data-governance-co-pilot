# pg-airman-mcp Helm Chart

PostgreSQL Model Context Protocol (MCP) server for AI agents. Provides database analysis tools including index tuning, explain plans, health checks, and SQL execution.

## Overview

This chart deploys the [pg-airman-mcp](https://github.com/EnterpriseDB/pg-airman-mcp) server as a standalone service that MCP clients can connect to.

## Important Note: Custom Image Build

**The official `enterprisedb/pg-airman-mcp` Docker image is missing the `libpq5` runtime library**, causing startup failures with:
```
ImportError: libpq.so.5: cannot open shared object file: No such file or directory
```

This chart **automatically builds a fixed custom image** using OpenShift BuildConfig with the proper PostgreSQL client libraries included. The build happens automatically during installation via the Makefile.

## Installation and Prerequisites

See the readme file in the root helm directory.

- Kubernetes cluster (OpenShift supported)
- PostgreSQL database (e.g., deployed via the `pgvector` chart)
- Helm 3.x
- **OpenShift**: BuildConfig support (for custom image build)

## Configuration

### Key Values

| Parameter | Description | Default |
|-----------|-------------|---------|
| `postgres.host` | PostgreSQL hostname | `pgvector-0.pgvector-postgres-service` |
| `postgres.port` | PostgreSQL port | `5432` |
| `postgres.user` | Database user | `<postgres userId>` (required) |
| `postgres.password` | Database password | `<postgres password>` (required) |
| `postgres.database` | Database name | `<postgres database>` (required) |
| `mcp.accessMode` | Access mode: `restricted` or `unrestricted` | `restricted` |
| `mcp.transport` | Transport: `stdio`, `sse`, or `streamable-http` | `streamable-http` |
| `mcp.port` | Port for SSE/HTTP transport | `8000` |
| `replicas` | Number of replicas | `1` |

**Important:** Use mcp.transport 'streamable-http' only. The other options are not supported by this quickstart.

### Access Modes

- **`restricted`** (recommended for production): Read-only operations, query timeout limits
- **`unrestricted`** (development only): Full read/write access

### Transport Options

**Important:** Use mcp.transport 'streamable-http' only. The other options are not supported by this quickstart.

- **`streamable-http`** (default): Simple HTTP request-response, works through proxies/load balancers
- **`sse`**: Server-Sent Events over HTTP (long-lived connections, streaming responses)
- **`stdio`**: Standard input/output (single client, process-based communication)

## MCP Tools Available

Once deployed, the server provides these MCP tools:

- `list_schemas` - Enumerate database schemas
- `list_objects` - Display tables, views, sequences
- `get_object_details` - Retrieve column info, constraints, indexes
- `execute_sql` - Run queries (respects access mode)
- `explain_query` - Generate execution plans
- `get_top_queries` - Identify slow queries (requires `pg_stat_statements`)
- `analyze_workload_indexes` - Recommend indexes
- `analyze_query_indexes` - Suggest indexes for specific SQL
- `analyze_db_health` - Check database health metrics
- `add_comment_to_object` - Document database objects

## Connecting from MCP Clients

### From Your Copilot Package

```python
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

async def connect_to_airman():
    async with streamable_http_client("http://pg-airman-mcp-service:8000") as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # List schemas
            result = await session.call_tool("list_schemas", {})
            print(result)
```

### As a Sidecar in Another Pod

This quickstart deploys the MCP server in its own pod, but other options, like sidecar deployments with the copilot backend may be possible with additional changes.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
spec:
  template:
    spec:
      containers:
      - name: app
        image: my-app:latest
        env:
        - name: MCP_SERVER_URL
          value: "http://localhost:8000"

      - name: pg-airman-mcp
        image: enterprisedb/pg-airman-mcp:latest
        args: ["--transport=sse", "--access-mode=restricted"]
        env:
        - name: DATABASE_URI
          valueFrom:
            secretKeyRef:
              name: pg-airman-mcp-secret
              key: DATABASE_URI
```

## Optional PostgreSQL Extensions

For enhanced functionality, install these extensions in your PostgreSQL database:

**Important:** These extensions are not enabled for this quickstart.

```sql
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;  -- Query performance analysis
CREATE EXTENSION IF NOT EXISTS hypopg;              -- Hypothetical index testing
```

## Troubleshooting

### Check Pod Status

```bash
oc get pods -l app.kubernetes.io/name=pg-airman-mcp
```

### View Logs

```bash
oc logs -l app.kubernetes.io/name=pg-airman-mcp -f
```

### Test Connection

```bash
# Port forward the service
oc port-forward svc/pg-airman-mcp-service 8000:8000

# Test health endpoint (if using SSE transport)
curl http://localhost:8000/health
```

## Security Considerations

- Use `restricted` access mode in production
- Store database credentials in OpenShift/Kubernetes secrets (handled automatically by this chart)
- Consider network policies to restrict which pods can access the MCP server
- Use TLS for external connections (configure via ingress/route)

## Resources

- [pg-airman-mcp GitHub](https://github.com/EnterpriseDB/pg-airman-mcp)
- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
