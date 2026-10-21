# Data Governance Copilot - System Architecture

> **Note:** Llama Stack mode (`PROVIDER_MODE=llama_stack`) is no longer supported by this quickstart, and deployments that used it should not be used. The backend source still contains a Llama Stack provider and the repository still contains a `copilot-llama-stack` Helm chart, but both are unsupported legacy code. This document describes the supported MCP Direct architecture only.

## High-Level Container Diagram

### Overview - Simplified View

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'fontSize': '18px', 'fontFamily': 'arial'}}}%%
graph TB
    USER["👤 User<br/><br/>Browser"]
    
    UI["📱 copilot-ui<br/><br/>Svelte App<br/>nginx:alpine<br/>Port 8080"]
    
    BE["⚙️ copilot-backend<br/><br/>FastAPI Service<br/>python:3.12<br/>Port 8080"]
    
    MCP["🔧 pg-airman-mcp<br/><br/>MCP Server<br/>10 PostgreSQL Tools<br/>Port 8000"]
    
    DB[("💾 pgvector<br/><br/>PostgreSQL 15<br/>E-commerce Data<br/>Port 5432")]
    
    LLM["🤖 vLLM<br/><br/>Inference Engine<br/>Nemotron/Qwen3<br/>Port 8000<br/>(Optional)"]
    
    USER ==>|"HTTPS"| UI
    
    UI ==>|"HTTP/SSE<br/>/query/stream"| BE
    
    BE ==>|"JSON-RPC"| MCP
    BE ==>|"OpenAI API"| LLM
    
    MCP ==>|"SQL"| DB
    
    style USER fill:#E8F5E9,stroke:#4CAF50,stroke-width:4px
    style UI fill:#E3F2FD,stroke:#2196F3,stroke-width:4px
    style BE fill:#FFF3E0,stroke:#FF9800,stroke-width:4px
    style MCP fill:#FCE4EC,stroke:#E91E63,stroke-width:4px
    style DB fill:#F3E5F5,stroke:#9C27B0,stroke-width:4px
    style LLM fill:#FFEBEE,stroke:#F44336,stroke-width:4px
```

vLLM is optional: the backend can use an external OpenAI-compatible model endpoint instead.

---

### Detailed Component Breakdown

#### 1️⃣ copilot-ui Pod

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'fontSize': '16px'}}}%%
graph LR
    A["nginx<br/>Web Server<br/>Port 8080"]
    B["Svelte App<br/>SPA Bundle"]
    C["Components<br/>ChatInterface<br/>MessageList<br/>PolicyUpload"]
    D["Local State<br/>Sessions<br/>Messages"]
    
    A --> B
    B --> C
    C --> D
    
    style A fill:#4CAF50,stroke:#388E3C,stroke-width:3px,color:#fff
    style B fill:#66BB6A,stroke:#388E3C,stroke-width:3px,color:#fff
    style C fill:#81C784,stroke:#388E3C,stroke-width:3px,color:#fff
    style D fill:#A5D6A7,stroke:#388E3C,stroke-width:3px,color:#fff
```

**Image:** `quay.io/rh-ai-quickstart/copilot-ui:latest`

---

#### 2️⃣ copilot-backend Pod

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'fontSize': '16px'}}}%%
graph TB
    A["FastAPI<br/>service.py<br/>9 Endpoints"]
    B["State Stores<br/>conversation_store<br/>governance_policy"]
    C["Provider Factory"]
    D1["MCP Direct<br/>Provider"]
    
    A --> B
    A --> C
    C --> D1
    
    style A fill:#2196F3,stroke:#1976D2,stroke-width:3px,color:#fff
    style B fill:#42A5F5,stroke:#1976D2,stroke-width:3px,color:#fff
    style C fill:#64B5F6,stroke:#1976D2,stroke-width:3px,color:#fff
    style D1 fill:#90CAF9,stroke:#1976D2,stroke-width:3px,color:#000
```

**Image:** `quay.io/rh-ai-quickstart/copilot-backend:latest`

---

#### 3️⃣ pg-airman-mcp Pod

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'fontSize': '16px'}}}%%
graph TB
    A["FastMCP Server<br/>JSON-RPC 2.0"]
    B["Transport Layer<br/>HTTP + SSE"]
    C["PostgreSQL Tools<br/>10 Total"]
    D1["Schema Tools<br/>list_schemas<br/>list_objects<br/>get_details"]
    D2["Query Tools<br/>execute_sql<br/>explain_query"]
    D3["Analysis Tools<br/>health_check<br/>index_analysis<br/>top_queries"]
    
    A --> B
    A --> C
    C --> D1
    C --> D2
    C --> D3
    
    style A fill:#FF9800,stroke:#F57C00,stroke-width:3px,color:#fff
    style B fill:#FFA726,stroke:#F57C00,stroke-width:3px,color:#fff
    style C fill:#FFB74D,stroke:#F57C00,stroke-width:3px,color:#000
    style D1 fill:#FFCC80,stroke:#F57C00,stroke-width:3px,color:#000
    style D2 fill:#FFE0B2,stroke:#F57C00,stroke-width:3px,color:#000
    style D3 fill:#FFF3E0,stroke:#F57C00,stroke-width:3px,color:#000
```

**Image:** `quay.io/rh-ai-quickstart/pg-airman-mcp:1.0.0`

---

#### 4️⃣ pgvector Pod

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'fontSize': '16px'}}}%%
graph LR
    A[("PostgreSQL 15<br/>Port 5432")]
    B["Extensions<br/>pgvector<br/>pg_stat_statements"]
    C["E-commerce Data<br/>Customers<br/>Orders<br/>Payments<br/>~45MB"]
    
    A --> B
    A --> C
    
    style A fill:#9C27B0,stroke:#7B1FA2,stroke-width:3px,color:#fff
    style B fill:#AB47BC,stroke:#7B1FA2,stroke-width:3px,color:#fff
    style C fill:#BA68C8,stroke:#7B1FA2,stroke-width:3px,color:#fff
```

**Image:** `quay.io/enterprisedb/postgresql:15`

---

#### 5️⃣ vLLM Pod (Optional)

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'fontSize': '16px'}}}%%
graph LR
    A["vLLM Engine<br/>GPU Inference"]
    B["Model Weights<br/>Nemotron-9B<br/>or Qwen3-14B"]
    C["OpenAI API<br/>/v1/chat/completions"]
    
    A --> B
    A --> C
    
    style A fill:#F44336,stroke:#D32F2F,stroke-width:3px,color:#fff
    style B fill:#EF5350,stroke:#D32F2F,stroke-width:3px,color:#fff
    style C fill:#E57373,stroke:#D32F2F,stroke-width:3px,color:#fff
```

**Deployment:** KServe InferenceService via OpenShift AI

---

## Orchestration: MCP Direct

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'fontSize': '18px'}}}%%
graph TB
    UI["📱 copilot-ui<br/><br/>Svelte Frontend"]
    
    BE["⚙️ copilot-backend<br/><br/>MCP Direct Provider<br/>Manages Agentic Loop"]
    
    MCP["🔧 pg-airman-mcp<br/><br/>Database Tools"]
    
    LLM["🤖 vLLM<br/><br/>LLM Inference<br/>(Optional)"]
    
    DB[("💾 pgvector<br/><br/>PostgreSQL")]
    
    UI ==>|"1. Query"| BE
    BE ==>|"2. OpenAI API"| LLM
    BE ==>|"3. JSON-RPC"| MCP
    MCP ==>|"4. SQL"| DB
    
    style UI fill:#E3F2FD,stroke:#2196F3,stroke-width:4px
    style BE fill:#FFF3E0,stroke:#FF9800,stroke-width:4px
    style MCP fill:#FCE4EC,stroke:#E91E63,stroke-width:4px
    style LLM fill:#FFEBEE,stroke:#F44336,stroke-width:4px
    style DB fill:#F3E5F5,stroke:#9C27B0,stroke-width:4px
```

**Active Components:** 5
- ✅ copilot-ui
- ✅ copilot-backend (MCP Direct mode)
- ✅ pg-airman-mcp
- ✅ pgvector
- ✅ vLLM (optional)

**Orchestration:** Backend manages complete agentic loop

---

## Component Details

### 1. copilot-ui (Frontend Container)

**Image**: `quay.io/rh-ai-quickstart/copilot-ui:latest`  
**Base**: `nginxinc/nginx-unprivileged:alpine`  
**Port**: 8080 (HTTP)

**Components**:
```
copilot-ui/
├── nginx (Web Server)
├── Svelte App (SPA)
│   ├── ChatInterface.svelte    # Main chat UI
│   ├── MessageList.svelte      # Display messages
│   ├── ChatInput.svelte        # User input
│   ├── PolicyUpload.svelte     # Policy management
│   ├── ChatHistory.svelte      # Session history
│   └── config.js               # Runtime config (backend URL)
└── Static Assets
    ├── index.html
    ├── bundle.js
    └── bundle.css
```

**State**:
- `currentSessionId` - Active conversation UUID
- `messages[]` - Current conversation messages
- `chatSessions[]` - All conversation history (localStorage)

**External Dependencies**:
- Backend API via HTTP/SSE

---

### 2. copilot-backend (Backend Container)

**Image**: `quay.io/rh-ai-quickstart/copilot-backend:latest`  
**Base**: `python:3.12-slim`  
**Port**: 8080 (HTTP)

**Components**:
```
copilot-backend/
├── FastAPI Application (service.py)
│   ├── 9 REST endpoints
│   ├── SSE streaming
│   └── CORS middleware
├── State Management
│   ├── conversation_store        # In-memory message history
│   └── governance_policy         # Global policy text
├── Provider Layer
│   ├── factory.py                # Provider selection
│   ├── base.py                   # LLMProvider interface
│   ├── mcp_direct.py             # MCP Direct implementation
│   └── llama_stack.py            # Legacy Llama Stack provider (unsupported)
└── Dependencies
    ├── fastapi
    ├── mcp[cli]                  # MCP SDK
    ├── llama-stack-client        # Used only by the legacy Llama Stack provider
    └── openai                    # For vLLM API
```

**State**:
- `conversation_store: dict[str, list[dict]]` - Conversation history
- `governance_policy: str | None` - Active policy
- MCP Direct provider: Single persistent MCP connection

**Environment Variables**:
- `COPILOT_PROVIDER_MODE` - "mcp_direct" (the only supported value)
- `LLM_BASE_URL` - vLLM endpoint
- `LLM_MODEL` - Model name
- `MCP_SERVER_URL` - pg-airman-mcp endpoint

**External Dependencies**:
- pg-airman-mcp (JSON-RPC)
- vLLM (OpenAI API)

---

### 3. pg-airman-mcp (MCP Server Container)

**Image**: `quay.io/rh-ai-quickstart/pg-airman-mcp:1.0.0`  
**Base**: `python:3.12-slim-bookworm`  
**Port**: 8000 (HTTP)

**Components**:
```
pg-airman-mcp/
├── FastMCP Server
│   ├── Transport: Streamable HTTP + SSE
│   └── Protocol: JSON-RPC 2.0
├── PostgreSQL Tools (10 total)
│   ├── Schema Discovery
│   │   ├── list_schemas           # List all schemas
│   │   ├── list_objects           # List tables/views/etc
│   │   └── get_object_details     # Table schema + comments
│   ├── Query Execution
│   │   ├── execute_sql            # Read-only SQL
│   │   └── explain_query          # Query plan analysis
│   ├── Performance Analysis
│   │   ├── analyze_workload_indexes    # Index recommendations
│   │   ├── analyze_query_indexes       # Query-specific indexes
│   │   └── get_top_queries             # Slow query analysis
│   ├── Health Monitoring
│   │   └── analyze_db_health      # Database health checks
│   └── Governance
│       └── add_comment_to_object  # Add metadata comments
└── PostgreSQL Client
    └── psycopg2 connection pool
```

**Patches Applied** (for OpenShift and MCP client compatibility):
1. DNS rebinding protection disabled
2. `list_schemas` noop parameter workaround

**Environment Variables**:
- `POSTGRES_HOST` - Database host
- `POSTGRES_PORT` - Database port (5432)
- `POSTGRES_USER` - Database user
- `POSTGRES_PASSWORD` - Database password
- `POSTGRES_DATABASE` - Database name

**External Dependencies**:
- PostgreSQL database

---

### 4. pgvector (Database Container)

**Image**: `quay.io/enterprisedb/postgresql:15`  
**Port**: 5432 (PostgreSQL)

**Components**:
```
pgvector/
├── PostgreSQL 15
├── Extensions
│   ├── pgvector                  # Vector similarity search
│   └── pg_stat_statements        # Query performance tracking
├── Sample Data (E-commerce)
│   ├── olist_customers_dataset.csv       (~45MB)
│   ├── olist_orders_dataset.csv
│   ├── olist_order_items_dataset.csv
│   └── olist_order_payments_dataset.csv
└── Schemas
    └── public
        ├── olist_customers (table)
        ├── olist_orders (table)
        ├── olist_order_items (table)
        └── olist_order_payments (table)
```

**Data Volume**: ~45MB CSV data  
**Initial Load**: Kubernetes Job (data-loader)

**Storage**:
- PersistentVolumeClaim for data directory

---

### 5. vLLM (LLM Inference Container - Optional)

**Image**: Custom (via KServe InferenceService)  
**Base**: `vllm/vllm-openai:latest`  
**Port**: 8000 (HTTP)

**Components**:
```
vLLM/
├── vLLM Engine
│   ├── Model loading
│   ├── Tensor parallelism
│   ├── PagedAttention
│   └── Continuous batching
├── OpenAI-Compatible API
│   ├── /v1/chat/completions     # Chat API
│   ├── /v1/completions          # Completion API
│   └── /v1/models               # Model info
└── Model Weights
    ├── Nemotron-9B (NVIDIA) OR
    └── Qwen3-14B-AWQ (Qwen)
```

**Configuration** (via vLLM args):
- `--served-model-name` - Model identifier
- `--max-model-len` - Context window (32768)
- `--enable-auto-tool-choice` - Tool calling support
- `--tool-call-parser` - "nemotron" or default
- `--chat-template` - Model-specific format

**GPU Requirements**:
- Nemotron-9B: 1x NVIDIA A10 (24GB) minimum
- Qwen3-14B-AWQ: 1x NVIDIA A10 (24GB) minimum

**External Dependencies**: None (self-contained)

---

## Network Communication

### Protocols Used

| Source | Target | Protocol | Port | Purpose |
|--------|--------|----------|------|---------|
| Browser | copilot-ui | HTTPS | 443 | UI access |
| copilot-ui | copilot-backend | HTTP + SSE | 8080 | API calls |
| copilot-backend | pg-airman-mcp | JSON-RPC (HTTP) | 8000 | Tool execution |
| copilot-backend | vLLM | OpenAI API (HTTP) | 8000 | LLM inference |
| pg-airman-mcp | pgvector | PostgreSQL | 5432 | SQL queries |

---

## Data Flow: User Query

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'fontSize': '16px'}}}%%
sequenceDiagram
    autonumber
    
    actor User
    participant UI as 📱 UI<br/>Svelte
    participant BE as ⚙️ Backend<br/>FastAPI
    participant PRV as 🔄 Provider<br/>MCP Direct
    participant LLM as 🤖 vLLM<br/>Model
    participant MCP as 🔧 MCP<br/>Tools
    participant DB as 💾 DB<br/>PostgreSQL

    User->>UI: Enter query
    UI->>BE: POST /query/stream
    Note over UI,BE: SSE connection opened
    BE->>PRV: process_query_stream()
    
    rect rgb(255, 245, 230)
        Note over PRV,DB: Agentic Loop - Iteration 1
        PRV->>LLM: Generate with tools
        LLM-->>PRV: Tool: execute_sql
        BE-->>UI: SSE: tool_call
        
        PRV->>MCP: call_tool("execute_sql")
        MCP->>DB: SELECT query
        DB-->>MCP: Results
        MCP-->>PRV: JSON result
        BE-->>UI: SSE: tool_result
    end
    
    rect rgb(230, 245, 255)
        Note over PRV,LLM: Agentic Loop - Final Response
        PRV->>LLM: Continue with data
        LLM-->>PRV: Answer text
        BE-->>UI: SSE: content_delta
    end
    
    PRV-->>BE: Complete
    BE->>BE: Save conversation
    BE-->>UI: SSE: final_response
    UI->>User: Display answer
```

---

## Deployment Topology

### OpenShift Resources

```
Namespace: <user-namespace>
│
├── Deployments
│   ├── copilot-ui (1 replica)
│   ├── copilot-backend (1 replica)
│   ├── pg-airman-mcp (1 replica)
│   └── postgres (1 replica)
│
├── Services
│   ├── copilot-ui-service (ClusterIP:8080)
│   ├── copilot-backend-service (ClusterIP:8080)
│   ├── pg-airman-mcp-service (ClusterIP:8000)
│   └── postgres-service (ClusterIP:5432)
│
├── Routes
│   ├── copilot-ui (HTTPS, edge termination)
│   └── copilot-backend (optional, for debugging)
│
├── ConfigMaps
│   ├── copilot-ui-config (config.js)
│   └── postgres-init-scripts
│
├── Secrets
│   ├── postgres-credentials
│   └── llm-api-key (if external LLM)
│
├── PersistentVolumeClaims
│   └── postgres-data (10Gi)
│
├── Jobs
│   └── pgvector-data-loader (runs once)
│
└── InferenceServices (if DEPLOY_MODEL=true)
    ├── nemotron-model OR
    └── qwen3-model
```

---

## Scaling Characteristics

| Component | Scalable? | Bottleneck | Notes |
|-----------|-----------|------------|-------|
| copilot-ui | ✅ Horizontal | None | Stateless |
| copilot-backend | ⚠️ Limited | conversation_store in-memory | Need Redis for multi-replica |
| pg-airman-mcp | ✅ Horizontal | Database connections | Connection pooling |
| pgvector | ❌ Single | PostgreSQL replication | Primary-replica setup needed |
| vLLM | ✅ Vertical (GPU) | GPU memory | Tensor parallelism for large models |

---

## Security Boundaries

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'fontSize': '18px'}}}%%
graph TB
    subgraph ZONE1["🌐 PUBLIC ZONE"]
        INTERNET["Internet<br/><br/>External Users"]
    end

    subgraph ZONE2["🛡️ EDGE ZONE"]
        ROUTE["OpenShift Route<br/><br/>TLS Termination<br/>HTTPS → HTTP"]
    end

    subgraph ZONE3["🏢 APPLICATION ZONE<br/><br/>ClusterIP Network"]
        UI["copilot-ui<br/>Port 8080"]
        BE["copilot-backend<br/>Port 8080"]
        MCP["pg-airman-mcp<br/>Port 8000"]
    end

    subgraph ZONE4["💾 DATA ZONE<br/><br/>ClusterIP Network"]
        DB[("pgvector<br/>Port 5432")]
    end

    subgraph ZONE5["⚡ COMPUTE ZONE<br/><br/>GPU Nodes"]
        LLM["vLLM<br/>Port 8000"]
    end

    INTERNET ==>|"HTTPS<br/>Port 443"| ROUTE
    ROUTE ==>|"HTTP<br/>Port 8080"| UI
    UI ==>|"HTTP"| BE
    BE ==>|"HTTP"| MCP
    BE ==>|"HTTP"| LLM
    MCP ==>|"PostgreSQL<br/>Port 5432"| DB

    style ZONE1 fill:#FFEBEE,stroke:#F44336,stroke-width:4px
    style ZONE2 fill:#FFF3E0,stroke:#FF9800,stroke-width:4px
    style ZONE3 fill:#E3F2FD,stroke:#2196F3,stroke-width:4px
    style ZONE4 fill:#F3E5F5,stroke:#9C27B0,stroke-width:4px
    style ZONE5 fill:#FCE4EC,stroke:#E91E63,stroke-width:4px
    
    style INTERNET fill:#EF5350,stroke:#D32F2F,stroke-width:3px,color:#fff
    style ROUTE fill:#FFA726,stroke:#F57C00,stroke-width:3px,color:#fff
    style UI fill:#42A5F5,stroke:#1976D2,stroke-width:3px,color:#fff
    style BE fill:#42A5F5,stroke:#1976D2,stroke-width:3px,color:#fff
    style MCP fill:#42A5F5,stroke:#1976D2,stroke-width:3px,color:#fff
    style DB fill:#AB47BC,stroke:#7B1FA2,stroke-width:3px,color:#fff
    style LLM fill:#EC407A,stroke:#C2185B,stroke-width:3px,color:#fff
```

**Security Layers:**

| Zone | Trust Level | Components | Exposure |
|------|-------------|------------|----------|
| 🌐 **Public** | Untrusted | Internet | External |
| 🛡️ **Edge** | Border | OpenShift Route | TLS termination |
| 🏢 **Application** | Trusted | UI, Backend, MCP | Internal only |
| 💾 **Data** | Highly Trusted | PostgreSQL | Internal only |
| ⚡ **Compute** | Trusted | vLLM (GPU) | Internal only |

**Current Security Posture:**
- ✅ TLS encryption at edge
- ⚠️ No authentication on API endpoints
- ⚠️ No authorization/RBAC
- ✅ Database credentials in Secret
- ✅ All internal services use ClusterIP (not exposed)

**Security Layers**:
1. **Ingress**: TLS termination at Route (edge)
2. **Application**: No authentication (add JWT/OAuth for production)
3. **Data**: Database credentials via Secret
4. **Network**: All internal communication over ClusterIP (not exposed)

---

## Configuration Matrix

| Component | Config Source | Runtime Configurable? |
|-----------|---------------|----------------------|
| copilot-ui | ConfigMap (config.js) | ✅ Yes (backend URL) |
| copilot-backend | Environment Variables | ✅ Yes (all params) |
| pg-airman-mcp | Environment Variables | ✅ Yes (DB connection) |
| pgvector | Environment Variables | ❌ No (requires restart) |
| vLLM | InferenceService args | ❌ No (model load time) |

---

## Build vs. Pull Strategy

Components can be pulled from Quay or built on the cluster (except pg-airman-mcp, which is always pulled):

### Pull from Quay (Default)
```yaml
BUILD_COPILOT_UI=false       # Default
BUILD_COPILOT_BACKEND=false  # Default
BUILD_PG_AIRMAN_MCP=false    # Default
BUILD_DATA_LOADER=false      # Default
```

**Benefits**:
- ✅ Faster deployment
- ✅ Less cluster compute
- ✅ Pre-tested images

### Build on Cluster
```yaml
BUILD_COPILOT_UI=true
BUILD_COPILOT_BACKEND=true
BUILD_DATA_LOADER=true
```

pg-airman-mcp is always pulled from Quay (pinned to v1.0.0 by digest); building it on the cluster is currently unsupported.

**Benefits**:
- ✅ Custom modifications
- ✅ No external registry dependency
- ✅ Development workflow

**Mechanism**: OpenShift BuildConfig + ImageStream

---

## Resource Requirements

### Minimum Cluster

| Component | CPU | Memory | Storage | GPU |
|-----------|-----|--------|---------|-----|
| copilot-ui | 100m | 128Mi | - | - |
| copilot-backend | 500m | 512Mi | - | - |
| pg-airman-mcp | 250m | 256Mi | - | - |
| pgvector | 500m | 1Gi | 10Gi PVC | - |
| vLLM (Nemotron-9B) | 4000m | 16Gi | - | 1x A10 (24GB) |
| vLLM (Qwen3-14B) | 4000m | 16Gi | - | 1x A10 (24GB) |
| **Total (w/ LLM)** | **5.35 CPU** | **~18Gi RAM** | **10Gi** | **1 GPU** |

### Recommended Cluster

- **Worker Nodes**: 3+ nodes
- **GPU Nodes**: 1+ node with NVIDIA GPU
- **GPU Type**: NVIDIA A100 (40GB/80GB) or L40 (48GB)
- **RAM per Worker**: 64GB
- **OpenShift**: 4.20.14+
- **OpenShift AI**: 3.2+

---

**Last Updated**: 2026-10-21  
**Architecture Version**: 0.1.0
