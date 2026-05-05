# Data Governance Copilot API Endpoints

Complete REST API documentation for the copilot backend service.

---

## API Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                   FastAPI Backend Service                       │
│                    (service.py)                                 │
└─────────────────────────────────────────────────────────────────┘

╔═══════════════════════════════════════════════════════════════╗
║                     HEALTH & INFO                              ║
╚═══════════════════════════════════════════════════════════════╝

GET  /health
     ├─ Returns: { status, provider_healthy, tools_available, provider_mode }
     └─ Purpose: Health check and system status

GET  /provider/info
     ├─ Returns: { provider_mode, requires_restart_on_policy_update, tool_count }
     └─ Purpose: Get provider capabilities and configuration


╔═══════════════════════════════════════════════════════════════╗
║                    QUERY PROCESSING                            ║
╚═══════════════════════════════════════════════════════════════╝

POST /query/stream
     ├─ Request:  QueryRequest { query, conversation_id?, enable_reasoning }
     ├─ Response: Server-Sent Events (SSE) stream
     ├─ Events:   query_start, iteration_start, llm_thinking,
     │            llm_content_delta, tool_call, tool_result,
     │            timing_summary, final_response, error
     └─ Purpose:  Process user query with real-time progress updates


╔═══════════════════════════════════════════════════════════════╗
║                    TOOL DISCOVERY                              ║
╚═══════════════════════════════════════════════════════════════╝

GET  /tools
     ├─ Returns: { tools: [...], count }
     └─ Purpose: List available MCP tools with schemas


╔═══════════════════════════════════════════════════════════════╗
║                 CONVERSATION MANAGEMENT                        ║
╚═══════════════════════════════════════════════════════════════╝

GET  /conversations
     ├─ Returns: { conversations: [{id, message_count, last_message}], total }
     └─ Purpose: List active conversations (debugging)

DELETE /conversations/{conversation_id}
       ├─ Returns: { status: "deleted", conversation_id }
       └─ Purpose: Delete conversation and associated session


╔═══════════════════════════════════════════════════════════════╗
║                   POLICY MANAGEMENT                            ║
╚═══════════════════════════════════════════════════════════════╝

GET  /policy/status
     ├─ Returns: PolicyStatusResponse { has_policy, policy_length, policy_preview }
     └─ Purpose: Check current policy status

POST /policy/upload
     ├─ Request:  PolicyUploadRequest { policy_text, conversation_id? }
     ├─ Returns:  PolicyResponse { status, policy_length, message, provider_mode, requires_restart }
     └─ Purpose:  Upload/replace governance policy

DELETE /policy
       ├─ Returns: PolicyResponse { status, message, provider_mode, requires_restart }
       └─ Purpose: Remove active governance policy
```

---

## Endpoint Details

### 1. Health & Info Endpoints

#### `GET /health`
**Purpose**: System health check

**Response**:
```json
{
  "status": "healthy",
  "provider_healthy": true,
  "tools_available": 10,
  "provider_mode": "mcp_direct"
}
```

**Use Case**: 
- Kubernetes liveness/readiness probes
- UI connection status indicator

---

#### `GET /provider/info`
**Purpose**: Get provider capabilities and requirements

**Response**:
```json
{
  "provider_mode": "mcp_direct",
  "requires_restart_on_policy_update": false,
  "tool_count": 10
}
```

**Use Case**:
- UI determines whether to show restart warning before policy upload
- Display which provider mode is active

---

### 2. Query Processing Endpoint

#### `POST /query/stream`
**Purpose**: Process user query with streaming progress

**Request** (`QueryRequest`):
```json
{
  "query": "Show me all customers",
  "conversation_id": "abc-123-def",  // Optional
  "enable_reasoning": true           // Optional (default: true)
}
```

**Response**: Server-Sent Events (text/event-stream)

**Event Types**:

| Event Type | Description | Example Payload |
|------------|-------------|-----------------|
| `query_start` | Query processing begins | `{type: "query_start", query: "...", timestamp: "14:30:15"}` |
| `iteration_start` | New agentic iteration | `{type: "iteration_start", iteration: 1, max_iterations: 100}` |
| `llm_thinking` | LLM reasoning process | `{type: "llm_thinking", content: "...", iteration: 1}` |
| `llm_content_delta` | Streaming response text | `{type: "llm_content_delta", content: "Here...", iteration: 1}` |
| `tool_call` | Tool execution starts | `{type: "tool_call", tool_name: "execute_sql", arguments: {...}}` |
| `tool_result` | Tool execution completes | `{type: "tool_result", tool_name: "...", mcp_time: 0.234}` |
| `timing_summary` | Performance breakdown | `{type: "timing_summary", total_time: 3.45, llm_time: 2.1, ...}` |
| `final_response` | Complete answer | `{type: "final_response", content: "...", conversation_id: "..."}` |
| `error` | Error occurred | `{type: "error", message: "...", traceback: "..."}` |

**Use Case**:
- Main query processing for chat interface
- Real-time progress updates during tool execution
- Conversation continuity via conversation_id

---

### 3. Tool Discovery Endpoint

#### `GET /tools`
**Purpose**: List available MCP tools

**Response**:
```json
{
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "list_schemas",
        "description": "List all schemas in the database",
        "parameters": {
          "type": "object",
          "properties": {
            "noop": {
              "type": "string",
              "description": "Workaround parameter, always use 'doit'"
            }
          },
          "required": ["noop"]
        }
      }
    }
    // ... 9 more tools
  ],
  "count": 10
}
```

**Use Case**:
- Debugging: verify available tools
- Documentation: auto-generate tool reference
- UI: show available capabilities to users

---

### 4. Conversation Management Endpoints

#### `GET /conversations`
**Purpose**: List all active conversations (debugging)

**Response**:
```json
{
  "conversations": [
    {
      "id": "abc-123-def",
      "message_count": 8,
      "last_message": "Here are the top 10 customers..."
    }
  ],
  "total": 1
}
```

**Use Case**:
- Debugging conversation state
- Monitoring active sessions
- Understanding memory usage

---

#### `DELETE /conversations/{conversation_id}`
**Purpose**: Delete conversation and associated session

**Path Parameter**: `conversation_id` (string)

**Response**:
```json
{
  "status": "deleted",
  "conversation_id": "abc-123-def"
}
```

**Side Effects**:
- Deletes message history from conversation_store
- Deletes Llama Stack session (if using llama_stack provider)

**Use Case**:
- User starts new conversation
- Clear conversation history
- Free up memory

---

### 5. Policy Management Endpoints

#### `GET /policy/status`
**Purpose**: Check current governance policy status

**Response** (`PolicyStatusResponse`):

**No policy active**:
```json
{
  "has_policy": false,
  "policy_length": null,
  "policy_preview": null
}
```

**Policy active**:
```json
{
  "has_policy": true,
  "policy_length": 1234,
  "policy_preview": "Data Governance Policy v2.0\n\n1. PII Protection..."
}
```

**Use Case**:
- UI shows policy status indicator
- Display policy preview in settings
- Determine if upload button should say "Upload" or "Replace"

---

#### `POST /policy/upload`
**Purpose**: Upload or replace data governance policy

**Request** (`PolicyUploadRequest`):
```json
{
  "policy_text": "Data Governance Policy v2.0\n\n...",
  "conversation_id": "abc-123-def"  // Optional: delete this conversation if restart required
}
```

**Response** (`PolicyResponse`):

**MCP Direct mode** (no restart needed):
```json
{
  "status": "uploaded",
  "policy_length": 1234,
  "message": "Policy updated successfully. Will apply to new messages immediately.",
  "provider_mode": "mcp_direct",
  "requires_restart": false
}
```

**Llama Stack mode** (restart required):
```json
{
  "status": "uploaded",
  "policy_length": 1234,
  "message": "Policy updated successfully. Agent recreated - all conversations must be restarted.",
  "provider_mode": "llama_stack",
  "requires_restart": true
}
```

**Side Effects**:
- Updates global `governance_policy` variable
- Calls `provider.update_governance_policy()`
- If `requires_restart=true` and `conversation_id` provided:
  - Deletes that conversation
  - Deletes associated Llama Stack session

**Use Case**:
- User uploads governance policy via UI
- Replace existing policy with new version
- Apply policy to all future conversations

---

#### `DELETE /policy`
**Purpose**: Remove active governance policy

**Response** (`PolicyResponse`):

**MCP Direct mode**:
```json
{
  "status": "deleted",
  "policy_length": null,
  "message": "Policy deleted successfully. Will apply to new messages immediately.",
  "provider_mode": "mcp_direct",
  "requires_restart": false
}
```

**Llama Stack mode**:
```json
{
  "status": "deleted",
  "policy_length": null,
  "message": "Policy deleted successfully. Agent recreated - all conversations must be restarted.",
  "provider_mode": "llama_stack",
  "requires_restart": true
}
```

**Side Effects**:
- Sets global `governance_policy = None`
- Calls `provider.update_governance_policy(None)`
- Llama Stack: recreates agent without policy, invalidates all sessions

**Use Case**:
- User removes governance policy
- Return to default behavior (no policy enforcement)

---

## Request/Response Models

### QueryRequest
```python
class QueryRequest(BaseModel):
    query: str                        # User's question/request
    conversation_id: str | None       # Optional: maintain context
    enable_reasoning: bool = True     # Show thinking process?
```

### PolicyUploadRequest
```python
class PolicyUploadRequest(BaseModel):
    policy_text: str                  # Governance policy content
    conversation_id: str | None       # Optional: delete if restart needed
```

### PolicyResponse
```python
class PolicyResponse(BaseModel):
    status: str                       # "uploaded" or "deleted"
    policy_length: int | None         # Character count
    message: str | None               # Human-readable status
    provider_mode: str | None         # "mcp_direct" or "llama_stack"
    requires_restart: bool | None     # Must conversations restart?
```

### PolicyStatusResponse
```python
class PolicyStatusResponse(BaseModel):
    has_policy: bool                  # Is policy active?
    policy_length: int | None         # Character count
    policy_preview: str | None        # First 200 chars
```

---

## SSE Event Schema

All events have this base structure:
```json
{
  "type": "event_type",
  // ... event-specific fields
}
```

### Event Types Reference

| Type | Fields | When Sent |
|------|--------|-----------|
| `query_start` | `query`, `timestamp` | Query processing begins |
| `iteration_start` | `iteration`, `max_iterations` | New agentic iteration starts |
| `llm_thinking` | `content`, `iteration` | LLM reasoning (if enable_reasoning=true) |
| `llm_content_delta` | `content`, `iteration` | Streaming response chunk |
| `tool_call` | `tool_name`, `arguments`, `iteration` | Tool execution starts |
| `tool_result` | `tool_name`, `mcp_time`, `iteration` | Tool execution completes |
| `timing_summary` | `total_time`, `llm_time`, `mcp_time`, `backend_overhead`, `iterations`, `tool_calls`, `context_tokens_used`, `context_tokens_limit`, `context_usage_pct` | Query completes |
| `final_response` | `content`, `tool_calls`, `conversation_id` | Final answer ready |
| `error` | `message`, `traceback` | Error occurred |

---

## CORS Configuration

**Current**: Allows all origins (`allow_origins=["*"]`)

**Production Recommendation**: Restrict to specific domains
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://copilot-ui.example.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)
```

---

## Authentication & Security

**Current**: No authentication implemented

**Future Considerations**:
- API key authentication for `/query/stream`
- RBAC for policy management endpoints
- Rate limiting on query endpoint
- Request size limits for policy uploads

---

## State Management

### In-Memory Stores

1. **`conversation_store: dict[str, list[dict]]`**
   - Maps conversation_id → message history
   - Ephemeral (lost on pod restart)
   - Used to maintain context across queries

2. **`governance_policy: str | None`**
   - Single global policy text
   - Replaced (not versioned) on upload
   - Ephemeral (lost on pod restart)

3. **Provider-specific state**
   - MCP Direct: Single persistent MCP connection
   - Llama Stack: `_session_store` maps conversation_id → session_id

**Production Recommendation**: Persist to Redis or PostgreSQL

---

## Error Handling

All endpoints follow this pattern:

**Success**: Return appropriate response model with 200 OK

**Client Error (4xx)**:
- `400`: Invalid request (e.g., empty policy text)
- `404`: Resource not found (e.g., conversation not found, no policy active)

**Server Error (5xx)**:
- `500`: Internal error (e.g., provider initialization failed)
- `503`: Service unavailable (e.g., copilot not initialized)

**SSE Errors**: Sent as `error` event in stream
```json
{
  "type": "error",
  "message": "LLM API call failed: timeout",
  "traceback": "..."
}
```

---

## Performance Characteristics

| Endpoint | Latency | Notes |
|----------|---------|-------|
| `/health` | <10ms | Fast check |
| `/provider/info` | <10ms | Cached info |
| `/query/stream` | 1-30s | Depends on query complexity |
| `/tools` | <50ms | Returns cached tool list |
| `/conversations` | <10ms | In-memory lookup |
| `/policy/upload` | 10-500ms | Llama Stack: recreates agent |
| `/policy/status` | <10ms | In-memory check |

---

## Integration Examples

### UI Query Processing (TypeScript)
```typescript
const eventSource = new EventSource(
  `${backendUrl}/query/stream`,
  {
    method: 'POST',
    body: JSON.stringify({
      query: userInput,
      conversation_id: currentSessionId,
      enable_reasoning: true
    })
  }
);

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  switch (data.type) {
    case 'llm_content_delta':
      appendToMessage(data.content);
      break;
    case 'tool_call':
      showToolExecution(data.tool_name);
      break;
    case 'final_response':
      completeMessage(data.content);
      break;
    case 'error':
      showError(data.message);
      break;
  }
};
```

### Policy Upload (TypeScript)
```typescript
const response = await fetch(`${backendUrl}/policy/upload`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    policy_text: policyContent,
    conversation_id: currentSessionId
  })
});

const result: PolicyResponse = await response.json();

if (result.requires_restart) {
  showRestartWarning("All conversations must be restarted");
  clearConversations();
}
```

---

## OpenAPI/Swagger Documentation

FastAPI auto-generates interactive API documentation:

- **Swagger UI**: `http://localhost:8080/docs`
- **ReDoc**: `http://localhost:8080/redoc`
- **OpenAPI JSON**: `http://localhost:8080/openapi.json`

Access these endpoints when the backend is running for interactive testing.

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | Current | Initial API implementation |

---

**Generated from**: `packages/copilot/src/copilot/service.py`  
**Last Updated**: 2026-04-16
