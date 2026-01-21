# Copilot Backend Helm Chart

FastAPI backend service that orchestrates interactions between Nemotron LLM and pg-airman-mcp tools.

## Architecture

The copilot backend acts as the orchestration layer in a 3-pod architecture:

```
┌─────────────────┐
│  Svelte UI      │  Pod 1: Frontend (static web UI)
│  (Frontend)     │
└────────┬────────┘
         │ HTTP POST /query
         ↓
┌─────────────────┐
│ Copilot Backend │  Pod 2: FastAPI orchestration layer
│  (This Chart)   │  - Connects to Nemotron LLM
└────┬────────┬───┘  - Executes MCP tools
     │        │      - Implements agentic loop
     │        │
     ↓        ↓
┌─────────┐  ┌──────────────┐
│ Nemotron│  │ pg-airman-mcp│  Pod 3: MCP server
│  LLM    │  │  (MCP Server)│
└─────────┘  └──────────────┘
(vLLM in      (PostgreSQL
OpenShift AI)  analysis tools)
```

## Features

- **FastAPI REST API** with `/query` endpoint for processing user questions
- **OpenAI-compatible LLM integration** for Nemotron model
- **MCP tool orchestration** - automatic tool discovery and execution
- **Multi-turn conversations** - handles complex queries requiring multiple tool calls
- **Health checks** - `/health` endpoint for readiness/liveness probes
- **OpenShift Route** - automatic HTTPS ingress with TLS termination

## Prerequisites

1. **pg-airman-mcp server** must be deployed first:
   ```bash
   make pg-airman-mcp-install NAMESPACE=your-namespace \
     postgres.userId=postgres \
     postgres.password=yourpass \
     postgres.databaseName=yourdb
   ```

2. **Nemotron LLM** deployed in OpenShift AI (vLLM inference server)

## Installation

### Quick Install (via Makefile)

```bash
# From the helm/ directory
# For vLLM servers without authentication
make copilot-backend-install NAMESPACE=your-namespace \
  copilot.llmApiKey=not-needed

# For secured endpoints (OpenShift AI, etc.)
make copilot-backend-install NAMESPACE=your-namespace \
  copilot.llmBaseUrl=https://your-nemotron-endpoint/v1 \
  copilot.llmModel=nvidia/nemotron-nano-9b-v2 \
  copilot.llmApiKey=your-actual-api-key
```

**Security Note**:
- The API key is **required** and must be passed at deployment time
- **Never commit API keys to Git** - they're passed as Make parameters
- For unsecured vLLM endpoints, use `copilot.llmApiKey=not-needed`
- For production endpoints, use the actual API key from your LLM provider

The Makefile will:
1. Build custom Docker image via OpenShift BuildConfig (3-5 minutes first time)
2. Deploy Helm chart with all resources
3. Wait for deployment to be ready
4. Print service URL and public route

### Manual Install

1. Build the image:
   ```bash
   oc apply -f imagestream.yaml -n your-namespace
   oc apply -f buildconfig.yaml -n your-namespace
   oc start-build copilot-backend --from-dir=../../. --follow -n your-namespace
   ```

2. Install the chart:
   ```bash
   helm upgrade --install copilot-backend . \
     --namespace your-namespace \
     --set image.repository=image-registry.openshift-image-registry.svc:5000/your-namespace/copilot-backend \
     --set image.tag=latest \
     --set llm.baseUrl=http://nemotron-service:8000/v1 \
     --set llm.model=nvidia/nemotron-nano-9b-v2
   ```

## Configuration

### Values

| Parameter | Description | Default |
|-----------|-------------|---------|
| `replicaCount` | Number of replicas | `1` |
| `image.repository` | Image repository | `image-registry.openshift-image-registry.svc:5000/NAMESPACE/copilot-backend` |
| `image.tag` | Image tag | `latest` |
| `service.port` | Service port | `8080` |
| `route.enabled` | Enable OpenShift Route | `true` |
| `mcp.serviceUrl` | pg-airman-mcp service URL | `http://pg-airman-mcp-service:8000` |
| `llm.baseUrl` | Nemotron LLM API base URL | `http://nemotron-service:8000/v1` |
| `llm.model` | LLM model name | `nvidia/nemotron-nano-9b-v2` |
| `llm.apiKey` | LLM API key (stored in Secret) | `not-needed` |
| `resources.requests.cpu` | CPU request | `500m` |
| `resources.requests.memory` | Memory request | `512Mi` |
| `resources.limits.cpu` | CPU limit | `1000m` |
| `resources.limits.memory` | Memory limit | `1Gi` |

### Environment Variables

The deployment sets these environment variables automatically:

- `PG_AIRMAN_MCP_SERVICE_PORT` - MCP server URL (from `mcp.serviceUrl`)
- `LLM_BASE_URL` - LLM API endpoint (from `llm.baseUrl`)
- `LLM_MODEL` - LLM model name (from `llm.model`)
- `LLM_API_KEY` - LLM API key (from Secret, populated from `llm.apiKey`)

## API Endpoints

### POST /query

Process a user query through the LLM with MCP tool support.

**Request:**
```json
{
  "query": "Show me the database schemas",
  "conversation_id": "optional-conversation-id"
}
```

**Response:**
```json
{
  "response": "The database has 3 schemas: public, staging, and analytics...",
  "tool_calls": [
    {
      "tool": "list_schemas",
      "arguments": {},
      "result": "..."
    }
  ],
  "conversation_id": "optional-conversation-id"
}
```

### GET /health

Health check endpoint for readiness/liveness probes.

**Response:**
```json
{
  "status": "healthy",
  "mcp_connected": true,
  "tools_available": 10
}
```

### GET /tools

List available MCP tools.

**Response:**
```json
{
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "list_schemas",
        "description": "List all schemas in the database",
        "parameters": {...}
      }
    }
  ],
  "count": 10
}
```

## Usage Example

### From Command Line (via curl)

```bash
# Get the route URL
COPILOT_URL=$(oc get route copilot-backend -o jsonpath='{.spec.host}' -n your-namespace)

# Send a query
curl -X POST "https://${COPILOT_URL}/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the most expensive queries in the database?"
  }'
```

### From Svelte Frontend

```javascript
const response = await fetch('https://copilot-backend.example.com/query', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    query: userInput,
    conversation_id: sessionId
  })
});

const data = await response.json();
console.log(data.response);  // LLM's final answer
console.log(data.tool_calls);  // Tools that were executed
```

## How It Works

1. **User sends query** via POST /query
2. **Backend forwards to LLM** with list of available MCP tools
3. **LLM decides which tools to use** (or none if not needed)
4. **Backend executes tools via MCP** and collects results
5. **Results sent back to LLM** for processing
6. **Steps 3-5 repeat** until LLM has final answer
7. **Backend returns response** with answer and tool execution history

This implements an **agentic loop** where the LLM can make multiple tool calls to gather information before providing a final answer.

## Scaling

The copilot backend is stateless and can be scaled horizontally:

```bash
# Manual scaling
oc scale deployment/copilot-backend --replicas=3 -n your-namespace

# Enable autoscaling
helm upgrade copilot-backend . \
  --namespace your-namespace \
  --set autoscaling.enabled=true \
  --set autoscaling.minReplicas=2 \
  --set autoscaling.maxReplicas=5 \
  --set autoscaling.targetCPUUtilizationPercentage=80
```

## Troubleshooting

### Check pod logs
```bash
oc logs -f deployment/copilot-backend -n your-namespace
```

### Check health status
```bash
COPILOT_URL=$(oc get route copilot-backend -o jsonpath='{.spec.host}' -n your-namespace)
curl "https://${COPILOT_URL}/health"
```

### Port-forward for local testing
```bash
oc port-forward service/copilot-backend 8080:8080 -n your-namespace

# Test locally
curl -X POST "http://localhost:8080/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "List database schemas"}'
```

### Common Issues

**MCP connection failed:**
- Verify pg-airman-mcp is running: `oc get pods | grep pg-airman-mcp`
- Check MCP service URL in deployment: `oc describe deployment copilot-backend`

**LLM connection failed:**
- Verify Nemotron service is accessible
- Check LLM_BASE_URL environment variable
- Test LLM endpoint: `curl http://nemotron-service:8000/v1/models`

**Tool calls failing:**
- Check MCP server logs: `oc logs -f deployment/pg-airman-mcp`
- Verify database credentials in pg-airman-mcp secret

## Uninstallation

```bash
# Via Makefile
make copilot-backend-uninstall NAMESPACE=your-namespace

# Or manually
helm uninstall copilot-backend -n your-namespace
```

## Development

### Local Development

1. Install dependencies:
   ```bash
   cd packages/copilot
   uv sync
   ```

2. Set environment variables:
   ```bash
   export PG_AIRMAN_MCP_SERVICE_PORT=http://localhost:8000
   export LLM_BASE_URL=http://localhost:8001/v1
   export LLM_MODEL=nvidia/nemotron-nano-9b-v2
   ```

3. Run locally:
   ```bash
   uv run copilot
   # Or: python -m copilot
   ```

4. Access API at http://localhost:8080

### Testing the API

```python
import requests

response = requests.post(
    "http://localhost:8080/query",
    json={"query": "Show me the database schemas"}
)
print(response.json())
```

## Architecture Details

### Tool Calling Flow

```
User Query: "What indexes are missing in the users table?"

1. Backend → LLM: Send query + available tools
2. LLM → Backend: "Use analyze_missing_indexes tool with table=users"
3. Backend → MCP: Execute analyze_missing_indexes(table="users")
4. MCP → PostgreSQL: Run analysis queries
5. PostgreSQL → MCP: Return missing index recommendations
6. MCP → Backend: Tool results
7. Backend → LLM: Send tool results
8. LLM → Backend: "Based on the analysis, I recommend..."
9. Backend → User: Final response + tool execution history
```

### MCP Tool Format Conversion

MCP tools have this format:
```python
{
  "name": "list_schemas",
  "description": "List all schemas",
  "inputSchema": {...}
}
```

Backend converts to OpenAI format:
```python
{
  "type": "function",
  "function": {
    "name": "list_schemas",
    "description": "List all schemas",
    "parameters": {...}
  }
}
```

This allows the LLM to understand and invoke MCP tools using OpenAI's function calling syntax.
