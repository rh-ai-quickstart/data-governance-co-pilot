# Copilot Llama Stack Helm Chart

This Helm chart deploys a LlamaStackDistribution instance for the Data Governance Copilot application, providing an alternative LLM inference backend powered by Llama Stack on OpenShift AI.

## Overview

The Llama Stack distribution provides:
- **Inference**: Remote vLLM connection for model serving
- **Agents**: Meta-reference agent implementation with persistence
- **Safety**: Llama Guard for content safety checks
- **Vector I/O**: FAISS for vector operations
- **Tool Runtime**: MCP (Model Context Protocol) integration for database tools

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Copilot Backend (FastAPI)                          │
│  (when PROVIDER_MODE=llama_stack)                   │
└──────────────┬──────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────┐
│  Llama Stack Distribution                           │
│  ┌───────────────────────────────────────────────┐  │
│  │  Inference → vLLM Service                     │  │
│  │  Agents → Meta-reference (inline)             │  │
│  │  Tools → pg-airman-mcp (remote MCP)           │  │
│  │  Storage → SQLite (KV + SQL backends)         │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

## Prerequisites

- OpenShift cluster with OpenShift AI 3.2+ installed
- Llama Stack operator enabled (managed by OpenShift AI)
- vLLM model deployment (either via `DEPLOY_MODEL=true` or external)
- pg-airman-mcp service running in the same namespace

## Installation

### Option 1: Via Main Makefile (Recommended)

Deploy with Llama Stack mode:

```bash
make install NAMESPACE=myns \
  PROVIDER_MODE=llama_stack \
  DEPLOY_MODEL=true \
  postgres.userId=postgres \
  postgres.password=yourpass \
  postgres.databaseName=yourdb \
  minio.userId=minio \
  minio.password=miniopass \
  pgadmin.email=admin@example.com \
  pgadmin.password=adminpass
```

### Option 2: Standalone Installation

If you already have the required services running:

```bash
helm upgrade --install copilot-llama-stack . \
  --namespace myns \
  --set model.name=nvidia-nemotron-nano-9b-v2 \
  --set model.apiKey=your-api-key
```

## Configuration

### Key Values

| Parameter | Description | Default |
|-----------|-------------|---------|
| `distribution.name` | LlamaStackDistribution resource name | `copilot-llama-stack` |
| `distribution.imageName` | Llama Stack distribution image | `rh-dev` |
| `distribution.replicas` | Number of replicas | `1` |
| `model.name` | LLM model name | (auto-detected if DEPLOY_MODEL=true) |
| `model.url` | vLLM service URL | (auto-generated from model.name) |
| `model.apiKey` | vLLM API key | (auto-extracted if DEPLOY_MODEL=true) |
| `mcp.serviceName` | MCP service name | `pg-airman-mcp` |
| `mcp.port` | MCP service port | `8000` |
| `route.enabled` | Create OpenShift route | `true` |

### Storage Configuration

The chart configures persistent storage for:
- **Metadata**: Key-value store (SQLite) at `/opt/app-root/src/.llama/distributions/rh/metadata.db`
- **Conversations**: SQL store (SQLite) at `/opt/app-root/src/.llama/distributions/rh/conversations.db`
- **Agent State**: Key-value store (shared with metadata)
- **Agent Responses**: SQL store (shared with conversations)
- **Vector Embeddings**: Key-value store (shared with metadata)

## Verification

After deployment, verify the installation:

```bash
# Check LlamaStackDistribution status
oc get llamastackdistribution copilot-llama-stack -n myns

# Check pods
oc get pods -l app.kubernetes.io/name=copilot-llama-stack -n myns

# Check logs
oc logs -l app.kubernetes.io/name=copilot-llama-stack -n myns

# Test the API
ROUTE_URL=$(oc get route llama-stack-api -o jsonpath='{.spec.host}' -n myns)
curl -k https://$ROUTE_URL/v1/version
```

## Integration with Copilot Backend

When `PROVIDER_MODE=llama_stack`, the copilot backend will connect to the Llama Stack service instead of directly to vLLM. The Llama Stack service handles:
- LLM inference via vLLM
- Agent orchestration
- Tool execution via MCP
- Safety checks
- Vector operations

## Troubleshooting

### Pod CrashLoopBackOff

Check the logs for validation errors:

```bash
oc logs -l app.kubernetes.io/name=copilot-llama-stack -n myns --tail=50
```

Common issues:
- Missing or incorrect vLLM service URL
- Invalid API key
- MCP service not accessible
- Storage configuration errors

### Connection Issues

Verify services are reachable:

```bash
# Check vLLM service
oc get inferenceservice -n myns

# Check MCP service
oc get service pg-airman-mcp-service -n myns

# Check Llama Stack service (created by operator)
oc get service copilot-llama-stack-service -n myns
```

## Uninstallation

Via Makefile:

```bash
make uninstall NAMESPACE=myns
```

Or standalone:

```bash
helm uninstall copilot-llama-stack -n myns
```

This will remove all resources including PVCs created by the LlamaStackDistribution.

## References

- [Llama Stack Documentation](https://github.com/meta-llama/llama-stack)
- [OpenShift AI Llama Stack Operator](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_cloud_service)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)
