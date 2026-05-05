# Data Governance Copilot API - Visual Diagram

## REST API Endpoint Map

```mermaid
graph TB
    subgraph "Data Governance Copilot API"
        API[FastAPI Service<br/>service.py]
    end

    subgraph "Health & Info"
        H1[GET /health]
        H2[GET /provider/info]
    end

    subgraph "Query Processing"
        Q1[POST /query/stream<br/>SSE Streaming]
    end

    subgraph "Tool Discovery"
        T1[GET /tools]
    end

    subgraph "Conversation Management"
        C1[GET /conversations]
        C2[DELETE /conversations/:id]
    end

    subgraph "Policy Management"
        P1[GET /policy/status]
        P2[POST /policy/upload]
        P3[DELETE /policy]
    end

    API --> H1
    API --> H2
    API --> Q1
    API --> T1
    API --> C1
    API --> C2
    API --> P1
    API --> P2
    API --> P3

    H1 -.-> HC[Health Check<br/>Returns: status, provider_healthy]
    H2 -.-> PI[Provider Info<br/>Returns: provider_mode, requires_restart]

    Q1 -.-> QE[Query Events<br/>SSE: query_start, iteration_start,<br/>llm_thinking, llm_content_delta,<br/>tool_call, tool_result,<br/>timing_summary, final_response]

    T1 -.-> TL[Tool List<br/>Returns: 10 MCP tools with schemas]

    C1 -.-> CL[Conversation List<br/>Returns: all active conversations]
    C2 -.-> CD[Delete Conversation<br/>Also deletes Llama Stack session]

    P1 -.-> PS[Policy Status<br/>Returns: has_policy, policy_preview]
    P2 -.-> PU[Upload Policy<br/>May require conversation restart]
    P3 -.-> PD[Delete Policy<br/>May require conversation restart]

    style API fill:#2196F3,stroke:#1976D2,color:#fff
    style Q1 fill:#FF9800,stroke:#F57C00,color:#fff
    style P2 fill:#E91E63,stroke:#C2185B,color:#fff
    style P3 fill:#E91E63,stroke:#C2185B,color:#fff
```

---

## Request Flow Diagram

```mermaid
sequenceDiagram
    participant UI as UI (Svelte)
    participant API as FastAPI Service
    participant Provider as Provider Layer
    participant MCP as MCP Server
    participant LLM as vLLM

    Note over UI,LLM: User Query Flow

    UI->>API: POST /query/stream<br/>{query, conversation_id}
    API->>API: Get conversation history<br/>from conversation_store
    
    loop Agentic Loop
        API->>Provider: process_query_stream()
        Provider->>LLM: Generate with tools
        LLM-->>Provider: Tool call request
        
        API-->>UI: SSE: tool_call event
        
        Provider->>MCP: JSON-RPC: call_tool()
        MCP-->>Provider: Tool result
        
        API-->>UI: SSE: tool_result event
        
        Provider->>LLM: Continue with result
        LLM-->>Provider: Content delta
        
        API-->>UI: SSE: llm_content_delta
    end
    
    Provider-->>API: Final response
    API->>API: Save to conversation_store
    API-->>UI: SSE: final_response event
```

---

## Policy Upload Flow

```mermaid
sequenceDiagram
    participant UI as UI
    participant API as service.py
    participant Provider as Provider (mcp_direct or llama_stack)
    
    Note over UI,Provider: Policy Upload - MCP Direct Mode
    
    UI->>API: POST /policy/upload<br/>{policy_text}
    API->>API: Store in governance_policy
    API->>Provider: update_governance_policy(policy)
    
    alt MCP Direct Mode
        Provider->>Provider: Update self.governance_policy
        Provider-->>API: Success (no restart needed)
        API-->>UI: {requires_restart: false}
        Note over UI: New queries use new policy<br/>immediately
    else Llama Stack Mode
        Provider->>Provider: Recreate agent with new instructions
        Provider->>Provider: Clear session_store
        Provider-->>API: Success (restart required)
        API-->>UI: {requires_restart: true}
        Note over UI: All conversations must restart
    end
```

---

## Conversation State Management

```mermaid
graph LR
    subgraph "UI State"
        S1[currentSessionId<br/>crypto.randomUUID]
    end

    subgraph "Backend State (service.py)"
        S2[conversation_store<br/>session_id → messages]
        S3[governance_policy<br/>Global policy text]
    end

    subgraph "Provider State"
        S4A[MCP Direct<br/>Single MCP connection]
        S4B[Llama Stack<br/>_session_store<br/>conversation_id → session_id]
    end

    S1 -->|conversation_id| S2
    S2 -->|messages| S4A
    S2 -->|messages| S4B
    S3 -.->|Injected into system prompt| S4A
    S3 -.->|Injected into agent instructions| S4B

    style S1 fill:#4CAF50,stroke:#388E3C,color:#fff
    style S2 fill:#2196F3,stroke:#1976D2,color:#fff
    style S3 fill:#E91E63,stroke:#C2185B,color:#fff
    style S4A fill:#FF9800,stroke:#F57C00,color:#fff
    style S4B fill:#FF9800,stroke:#F57C00,color:#fff
```

---

## SSE Event Timeline

```mermaid
gantt
    title Query Processing Timeline (SSE Events)
    dateFormat  ss
    axisFormat  %Ss

    section Query
    query_start           :milestone, m1, 00, 0s

    section Iteration 1
    iteration_start       :milestone, m2, 00, 0s
    llm_thinking         :active, a1, 00, 2s
    tool_call (list_schemas) :crit, t1, 02, 1s
    tool_result          :milestone, m3, 03, 0s

    section Iteration 2
    iteration_start       :milestone, m4, 03, 0s
    tool_call (execute_sql)  :crit, t2, 03, 2s
    tool_result          :milestone, m5, 05, 0s

    section Final
    llm_content_delta    :active, a2, 05, 3s
    timing_summary       :milestone, m6, 08, 0s
    final_response       :milestone, m7, 08, 0s
```

---

## Error Handling Flow

```mermaid
graph TD
    Start[API Request] --> Validate{Valid Request?}
    
    Validate -->|No| E400[400 Bad Request<br/>Invalid parameters]
    Validate -->|Yes| Check{Resource Exists?}
    
    Check -->|No| E404[404 Not Found<br/>Conversation/Policy not found]
    Check -->|Yes| Process{Process Request}
    
    Process -->|Success| R200[200 OK<br/>Return response]
    Process -->|Provider Error| E500[500 Internal Error<br/>Provider failed]
    Process -->|Not Initialized| E503[503 Service Unavailable<br/>Copilot not ready]
    Process -->|Stream Error| SSE[SSE: error event<br/>In-stream error]
    
    style E400 fill:#f44336,color:#fff
    style E404 fill:#ff9800,color:#fff
    style E500 fill:#f44336,color:#fff
    style E503 fill:#ff9800,color:#fff
    style SSE fill:#ff9800,color:#fff
    style R200 fill:#4CAF50,color:#fff
```

---

## Endpoint Summary Table

| Category | Method | Endpoint | Auth | Streaming |
|----------|--------|----------|------|-----------|
| **Health** | GET | `/health` | ❌ | ❌ |
| **Health** | GET | `/provider/info` | ❌ | ❌ |
| **Query** | POST | `/query/stream` | ❌ | ✅ SSE |
| **Tools** | GET | `/tools` | ❌ | ❌ |
| **Conversations** | GET | `/conversations` | ❌ | ❌ |
| **Conversations** | DELETE | `/conversations/:id` | ❌ | ❌ |
| **Policy** | GET | `/policy/status` | ❌ | ❌ |
| **Policy** | POST | `/policy/upload` | ❌ | ❌ |
| **Policy** | DELETE | `/policy` | ❌ | ❌ |

**Total Endpoints**: 9

---

## Protocol Stack

```
┌─────────────────────────────────────┐
│         UI (Browser)                │
│      Svelte + TypeScript            │
└─────────────────────────────────────┘
              │
              │ HTTP/HTTPS + SSE
              ↓
┌─────────────────────────────────────┐
│      FastAPI (service.py)           │
│    REST + Server-Sent Events        │
└─────────────────────────────────────┘
              │
              │ Python API
              ↓
┌─────────────────────────────────────┐
│       Provider Layer                │
│  mcp_direct | llama_stack           │
└─────────────────────────────────────┘
          │           │
   JSON-RPC │         │ Llama Stack API
          │           │
    ┌─────▼───┐   ┌──▼──────┐
    │   MCP   │   │  Llama  │
    │ Server  │   │  Stack  │
    └─────────┘   └─────────┘
          │            │
          └────────────┘
                │
                │ OpenAI API
                ↓
         ┌────────────┐
         │    vLLM    │
         └────────────┘
```

---

**For full details**, see [API_ENDPOINTS.md](./API_ENDPOINTS.md)
