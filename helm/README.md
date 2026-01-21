# Helm Charts - Data Governance Copilot

This directory contains Helm charts for deploying the data governance solution components.

## Available Charts

- **pgvector** - PostgreSQL database with pgvector extension
- **minio** - Object storage for data assets
- **pgadmin** - Database administration UI
- **pg-airman-mcp** - MCP server for PostgreSQL database operations

## Quick Start

### Full Installation

Install all components (pgvector, minio, pgadmin):

```bash
make install \
  NAMESPACE=data-gov \
  postgres.userId=postgres \
  postgres.password=securepass123 \
  postgres.databaseName=governance \
  minio.userId=minio \
  minio.password=minio123 \
  pgadmin.email=admin@example.com \
  pgadmin.password=admin123
```

### Install pg-airman-mcp MCP Server

After installing the database, deploy the MCP server:

```bash
make pg-airman-mcp-install \
  NAMESPACE=data-gov \
  postgres.userId=postgres \
  postgres.password=securepass123 \
  postgres.databaseName=governance
```

Optional: Set access mode (default is `restricted` for production):

```bash
make pg-airman-mcp-install \
  NAMESPACE=data-gov \
  postgres.userId=postgres \
  postgres.password=securepass123 \
  postgres.databaseName=governance \
  pgairman.accessMode=unrestricted
```

## Access Modes

**pg-airman-mcp** supports two access modes:

- **`restricted`** (default, recommended for production):
  - Read-only operations
  - Query timeout limits
  - Safe for production environments

- **`unrestricted`** (development only):
  - Full read-write access
  - No query timeouts
  - Use only in development/testing

## Accessing Services

### pgAdmin

After installation, get the pgAdmin URL:

```bash
oc get route pgadmin -n data-gov -o jsonpath='{.spec.host}'
```

### pg-airman-mcp

The MCP server is available internally at:

```
http://pg-airman-mcp-service:8000/sse
```

To access from outside the cluster (for local development):

```bash
kubectl port-forward svc/pg-airman-mcp-service 8000:8000 -n data-gov
```

Then connect to: `http://localhost:8000/sse`

## Uninstallation

### Remove All Components

```bash
make uninstall NAMESPACE=data-gov
```

### Remove Only pg-airman-mcp

```bash
make pg-airman-mcp-uninstall NAMESPACE=data-gov
```

## Configuration Reference

### Required Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `NAMESPACE` | OpenShift/Kubernetes namespace | `data-gov` |
| `postgres.userId` | PostgreSQL username | `postgres` |
| `postgres.password` | PostgreSQL password | `securepass123` |
| `postgres.databaseName` | Database name | `governance` |

### Optional Parameters (for full install)

| Parameter | Description | Default |
|-----------|-------------|---------|
| `minio.userId` | MinIO username | - |
| `minio.password` | MinIO password | - |
| `pgadmin.email` | pgAdmin login email | - |
| `pgadmin.password` | pgAdmin password | - |
| `pgairman.accessMode` | MCP access mode | `restricted` |

## Chart Details

### pgvector Chart

Deploys PostgreSQL with:
- pgvector extension for vector operations
- StatefulSet for data persistence
- Data loading job for initial dataset
- Service for internal cluster access

### pg-airman-mcp Chart

Deploys MCP server with:
- Official `enterprisedb/pg-airman-mcp` Docker image
- SSE transport for HTTP-based MCP communication
- Configurable access mode (restricted/unrestricted)
- Health checks and readiness probes
- Service for client connections

**Available MCP Tools**:
- Schema introspection
- SQL execution
- Query analysis and explain plans
- Index recommendations
- Database health checks

See [pg-airman-mcp/README.md](pg-airman-mcp/README.md) for detailed documentation.

## Development Workflow

```bash
# 1. Install database and supporting services
make install NAMESPACE=dev \
  postgres.userId=dev postgres.password=dev123 postgres.databaseName=devdb \
  minio.userId=minio minio.password=minio123 \
  pgadmin.email=dev@example.com pgadmin.password=admin

# 2. Install MCP server in development mode
make pg-airman-mcp-install NAMESPACE=dev \
  postgres.userId=dev postgres.password=dev123 postgres.databaseName=devdb \
  pgairman.accessMode=unrestricted

# 3. Port-forward for local testing
kubectl port-forward svc/pg-airman-mcp-service 8000:8000 -n dev

# 4. Test MCP connection from copilot
cd ../packages/copilot
export PG_AIRMAN_MCP_SERVICE_PORT=http://localhost:8000
uv run copilot
```

## Troubleshooting

### Check Deployment Status

```bash
# All pods
oc get pods -n data-gov

# Specific service
oc get pods -l app.kubernetes.io/name=pg-airman-mcp -n data-gov
```

### View Logs

```bash
# pg-airman-mcp logs
oc logs -l app.kubernetes.io/name=pg-airman-mcp -n data-gov -f

# Database logs
oc logs pgvector-0 -n data-gov -f
```

### Test MCP Server

```bash
# Port forward
kubectl port-forward svc/pg-airman-mcp-service 8000:8000 -n data-gov

# Test health endpoint (if using SSE transport)
curl http://localhost:8000/health
```

### Common Issues

**MCP server not starting**:
- Check DATABASE_URI is correct: `oc get secret pg-airman-mcp-secret -o yaml`
- Verify database is accessible: `oc get pods -l app=pgvector`
- Check logs: `oc logs -l app.kubernetes.io/name=pg-airman-mcp`

**Connection refused from copilot**:
- Ensure service exists: `oc get svc pg-airman-mcp-service`
- Verify pod is running: `oc get pods -l app.kubernetes.io/name=pg-airman-mcp`
- Check network policies if any

## Architecture

```
┌────────────────────────────────────────────────────┐
│  OpenShift/Kubernetes Namespace                    │
│                                                    │
│  ┌──────────┐   ┌─────────────┐   ┌────────────┐ │
│  │  Copilot │──►│ pg-airman-  │──►│ PostgreSQL │ │
│  │ (Client) │   │ mcp (MCP)   │   │ (pgvector) │ │
│  └──────────┘   └─────────────┘   └────────────┘ │
│                                         │          │
│                                    ┌────▼─────┐   │
│                                    │  MinIO   │   │
│                                    └──────────┘   │
└────────────────────────────────────────────────────┘
```

## Next Steps

After deploying the infrastructure:

1. Install PostgreSQL extensions:
   ```sql
   CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
   CREATE EXTENSION IF NOT EXISTS hypopg;
   ```

2. Deploy the copilot application (see `packages/copilot/README.md`)

3. Configure MCP client to connect to `http://pg-airman-mcp-service:8000/sse`
