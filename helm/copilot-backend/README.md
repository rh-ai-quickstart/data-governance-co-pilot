# Copilot Backend Helm Chart

FastAPI backend service that orchestrates interactions between Nemotron LLM and pg-airman-mcp tools.

## Architecture

The copilot backend acts as the orchestration layer in a 3-pod architecture:

```
┌─────────────────┐
│  Svelte UI      │  Pod 1: Frontend (static web UI)
│  (Frontend)     │
└────────┬────────┘
         │ HTTP POST /query/stream (SSE)
         ↓
┌─────────────────┐
│ Copilot Backend │  Pod 2: FastAPI orchestration layer
│  (This Chart)   │  - Connects to Nemotron LLM
└────┬────────┬───┘  - Executes MCP tools (using Streaming HTTP)
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

- **FastAPI streaming API** with `/query/stream` endpoint (SSE) for real-time progress updates
- **OpenAI-compatible LLM integration** for Nemotron model
- **MCP tool orchestration** - automatic tool discovery and execution
- **Multi-turn conversations** - handles complex queries requiring multiple tool calls
- **Health checks** - `/health` endpoint for readiness/liveness probes
- **OpenShift Route** - automatic HTTPS ingress with TLS termination

## Installation and Prerequisites

See the helm chart root directory for installation directions and prerequisites.

1. **pg-airman-mcp server** must be deployed first:
2. **Nemotron LLM** deployed in OpenShift AI (vLLM inference server)

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

### POST /query/stream

Process a user query through the LLM with real-time progress streaming via Server-Sent Events (SSE).

**Request:**
```json
{
  "query": "Show me the database schemas",
  "conversation_id": "optional-conversation-id",
  "enable_reasoning": true
}
```

**Response (SSE Stream):**
Server sends multiple events as the query is processed:

```
data: {"type":"iteration_start","iteration":1,"max_iterations":100}

data: {"type":"llm_thinking","content":"I need to list the schemas...","iteration":1}

data: {"type":"tool_call","tool_name":"list_schemas","arguments":{},"iteration":1}

data: {"type":"tool_result","tool_name":"list_schemas","result":"...","iteration":1}

data: {"type":"final_response","content":"The database has 3 schemas...","tool_calls":[...]}

data: {"type":"timing_summary","total_time":2.5,"llm_time":1.2,"mcp_time":0.8,...}
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

# Send a streaming query (SSE)
curl -N -X POST "https://${COPILOT_URL}/query/stream" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "query": "What are the most expensive queries in the database?",
    "enable_reasoning": true
  }'
```

### From Svelte Frontend

```javascript
const response = await fetch('https://copilot-backend.example.com/query/stream', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'text/event-stream'
  },
  body: JSON.stringify({
    query: userInput,
    conversation_id: sessionId,
    enable_reasoning: true
  })
});

// Read SSE stream
const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;

  const chunk = decoder.decode(value);
  // Parse SSE events: "data: {...}\n\n"
  const events = chunk.split('\n\n').filter(e => e.startsWith('data: '));
  for (const event of events) {
    const data = JSON.parse(event.slice(6)); // Remove "data: " prefix
    console.log(data.type, data);
  }
}
```

## How It Works

1. **User sends query** via POST /query/stream (SSE)
2. **Backend streams iteration_start event** to indicate processing has begun
3. **Backend forwards to LLM** with list of available MCP tools
4. **LLM streams thinking content** (if reasoning enabled) - backend forwards as llm_thinking events
5. **LLM decides which tools to use** (or none if not needed)
6. **Backend streams tool_call events** and executes tools via MCP
7. **Backend streams tool_result events** with MCP results
8. **Results sent back to LLM** for processing
9. **Steps 4-8 repeat** until LLM has final answer
10. **Backend streams final_response and timing_summary events**

This implements an **agentic loop** with **real-time progress updates** via Server-Sent Events, allowing the frontend to display thinking, tool execution, and results as they happen.

## Scaling

This component has not been testing for horizontal scaling. 

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

# Test locally with SSE streaming
curl -N -X POST "http://localhost:8080/query/stream" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{"query": "List database schemas", "enable_reasoning": true}'
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

# Stream SSE events
response = requests.post(
    "http://localhost:8080/query/stream",
    headers={"Accept": "text/event-stream"},
    json={
        "query": "Show me the database schemas",
        "enable_reasoning": True
    },
    stream=True
)

# Parse SSE events
for line in response.iter_lines():
    if line and line.startswith(b'data: '):
        event_data = line[6:].decode('utf-8')  # Remove "data: " prefix
        print(event_data)
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
