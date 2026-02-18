# Data Governance Co-Pilot

Empower data analyst using AI-driven natural language queries integrated with their organization's data governance policy.

## Description

The Data Governance Co-Pilot enables analysts to interact with their databases using natural language while maintaining  governance controls. Instead of writing complex SQL queries, users can ask questions like "Show me all tables containing customer PII" or "What are the retention policies for user data?" and receive accurate, policy-compliant responses.

This quickstart demonstrates how to build an agentic AI application that combines Large Language Model (LLM) inference with database tools through the Model Context Protocol (MCP). The application supports two deployment architectures:

- **MCP-Direct Mode**: Backend manages the agentic loop with direct vLLM inference and MCP tool execution
- **Llama Stack Mode**: Leverages OpenShift AI's Llama Stack operator for agent orchestration with integrated MCP tools

Both modes provide the same user experience through a modern web interface with real-time streaming, reasoning transparency, and conversation management. The flexible architecture allows organizations to choose the deployment mode that best fits their infrastructure and operational requirements.

### Key Capabilities

- **Natural Language Database Queries**: Ask questions about database schema, policies, and data governance in plain English
- **Governance-Aware Responses**: Built-in awareness of data classification, retention policies, and access controls
- **Real-Time Streaming**: Watch the AI agent's reasoning process as it explores the database and formulates answers (the Llama Stack deployment route may provide limited reasoning output)
- **Tool Calling via MCP**: Database operations executed through the Model Context Protocol for secure, structured interactions
- **Multi-Model Support**: Works with Nemotron (custom tool calling format) and Llama 3.1 (OpenAI function calling) models
- **Dual Architecture**: Choose between backend-managed or Llama Stack-managed agentic orchestration

## Architecture

### High-Level Architecture

The Data Governance Co-Pilot consists of three main components:

1. **Web UI** (Svelte): Modern chat interface with streaming responses and reasoning visualization
2. **Backend Orchestrator** (FastAPI): Provider-based architecture supporting two deployment modes
3. **Database Tools** (EDB's pg-airman-mcp MCP Server and Postgres AI database): PostgreSQL introspection and query tools exposed via Model Context Protocol

```
┌─────────────────────────────────────────────────────────────┐
│                       Web Browser                           │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Svelte Chat Interface                   │   │
│  │  • Natural language input                            │   │
│  │  • Streaming responses with SSE                      │   │
│  │  • Reasoning transparency display                    │   │
│  │  • Conversation history management                   │   │
│  │  • Data governance policy management                 │   │
│  └────────────────────┬─────────────────────────────────┘   │
└───────────────────────┼─────────────────────────────────────┘
                        │ HTTPS
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              FastAPI Backend (OpenShift)                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         Provider Factory (Mode Selection)            │   │
│  └────────────┬─────────────┬───────────────────────────┘   │
│               │             │                               │
│   ┌───────────▼──────┐  ┌──▼─────────────────┐              │
│   │ MCP-Direct       │  │ Llama Stack        │              │
│   │ Provider         │  │ Provider           │              │
│   │                  │  │                    │              │
│   │ • OpenAI Client  │  │ • Llama Stack      │              │
│   │ • MCP Client     │  │   Client           │              │
│   │ • Loop Mgmt      │  │ • Agents API       │              │
│   │ • Model Format   │  │ • Event Mapping    │              │
│   │   Detection      │  │ • Stream Relay     │              │
│   └──────┬───────────┘  └────┬───────────────┘              │
│          │                   │                              │
└──────────┼───────────────────┼──────────────────────────────┘
           │                   │
           ▼                   ▼
┌──────────────────┐   ┌──────────────────┐
│ vLLM Models:     │   │  Llama Stack     │
│ • Nemotron       │   │  (OpenShift AI)  │
│ • Llama 3.1      │   │  • Agents API    │
│                  │   │  • Tool Runtime  │
└──────┬───────────┘   └────┬─────────────┘
       │                    │
       └────────────────────┘
                │
        ┌───────▼────────┐
        │  MCP Server    │
        │  (pg-airman)   │
        │                │
        │ • Schema       │
        │   introspection│
        │ • Policy query │
        │ • Data catalog │
        └───────┬────────┘
                │
                ▼
        ┌──────────────────┐
        │  EDB Postgre AI  │
        │    PostgreSQL    │
        │     Database     │
        └──────────────────┘
```

### Architecture Modes

#### MCP-Direct Mode

In this mode, the FastAPI backend manages the complete agentic loop:

1. Receives natural language query from UI
2. Calls vLLM model with available tools
3. Parses model response (supports Nemotron custom tags or OpenAI function calling)
4. Executes tool calls via MCP client
5. Continues iteration until final answer is reached
6. Streams all events (reasoning, tool calls, results) to UI
7. Positioned for future custom enhancements, including intelligent context optimization technique

**Best for**: Organizations wanting full control over agentic orchestration, custom model formats, or detailed event granularity.

#### Llama Stack Mode

In this mode, Llama Stack (OpenShift AI) manages the agentic loop:

1. Backend registers MCP tools as a toolgroup with Llama Stack
2. Creates an agent with access to the toolgroup
3. Receives natural language query from UI
4. Delegates to Llama Stack Agents API for orchestration
5. Llama Stack executes the agentic loop (tool calling, iteration)
6. Backend streams and maps Llama Stack events to UI format

**Best for**: Organizations leveraging OpenShift AI infrastructure, preferring managed agent orchestration, or using standard OpenAI-compatible models. Note that Llama Stack supports both turn- and step-based inference. In this quickstart, we use it's ability to implement fire-and-forget, turn-based inference.

### Technology Stack

- **Frontend**: Svelte 5, TypeScript, TailwindCSS, Server-Sent Events (SSE)
- **Backend**: Python 3.12, FastAPI, OpenAI Python SDK, MCP SDK
- **LLM Inference**:
  - MCP-Direct: vLLM (supports Nemotron, Llama 3.1)
  - Llama Stack: OpenShift AI Llama Stack Operator
- **Tool Runtime**: Model Context Protocol (MCP) server for PostgreSQL (pg-airman-mcp)
- **Database**: PostgreSQL (EDB Postgres AI database)
- **Platform**: OpenShift Container Platform 4.x

## Requirements

### Minimum Hardware Requirements

- **OpenShift Cluster**: 3+ worker nodes
- **GPU Nodes**: At least 1 node with NVIDIA GPU (for LLM inference)
  - Recommended: NVIDIA A100, A10, or L40 (24GB+ VRAM)
  - Minimum: NVIDIA T4 (16GB VRAM)
- **Memory**: 32GB RAM per worker node (minimum)
- **Storage**: 100GB persistent storage for model weights and application data

### Minimum Software Requirements

- **OpenShift Container Platform**: Version 4.14 or higher
- **NVIDIA GPU Operator**: For GPU support on OpenShift
- **Helm**: Version 3.8 or higher
- **oc CLI**: OpenShift command-line tool (matching cluster version)
- **PostgreSQL Database**: Version 12 or higher
  - Can be deployed as part of this quickstart or use existing instance
  - Database credentials required for deployment

### Optional Requirements (Llama Stack Mode)

- **OpenShift AI**: Version 3.2 or higher
- **Llama Stack Operator**: Included with OpenShift AI 3.2+

## Deploy

### Prerequisites

1. **Access to OpenShift Cluster**:
   ```bash
   oc login <your-cluster-url>
   ```

2. **Clone the Repository**:
   ```bash
   git clone https://github.com/your-org/data-governance-co-pilot.git
   cd data-governance-co-pilot
   ```

3a. **Full Installation (with llama stack backend)**:
   ```bash
   make install NAMESPACE=your-namespace PROVIDER_MODE=llama_stack DEPLOY_MODEL=true postgres.userId=postgres postgres.password=postgres postgres.databaseName=postgres minio.userId=minio minio.password=minio1234! pgadmin.email=yourname@redhat.com pgadmin.password=postgres
   ```
3b. **Full Installation (with MCP direct backend)**:
   ```bash
   make install NAMESPACE=your-namespace PROVIDER_MODE=mcp_direct DEPLOY_MODEL=true postgres.userId=postgres postgres.password=postgres postgres.databaseName=postgres minio.userId=minio minio.password=minio1234! pgadmin.email=yourname@redhat.com pgadmin.password=postgres
   ```

You can also deploy the quickstart using an existing model. Specify DEPLOY_MODEL=false and provide the URL endpoint and model name in the values.yaml file in the copilot-backend and copilot-llama-stack project. You must then provide the api key at the terminal by setting copilot.llmApiKey=your_key_here.

### Deployment Options

The application supports two deployment modes. Choose the one that fits your infrastructure:

#### Option 1: MCP-Direct Mode (Default)

This mode deploys a vLLM model instance and manages the agentic loop in the backend.

**Deploy with Nemotron Model** (default):
```bash
make install NAMESPACE=$NAMESPACE \
  PROVIDER_MODE=mcp_direct \
  DEPLOY_MODEL=true \
  postgres.userId=<your-db-user> \
  postgres.password=<your-db-password> \
  postgres.host=<your-db-host> \
  postgres.port=5432 \
  postgres.database=<your-db-name>
```

**Deploy with Llama 3.1 Model** (requires vLLM with function calling support):
```bash
# The application will automatically deploy Llama 3.1 vLLM instance with required flags:
# --enable-auto-tool-choice --tool-call-parser llama3_json

make install NAMESPACE=$NAMESPACE \
  PROVIDER_MODE=mcp_direct \
  llm.model=meta-llama/Llama-3.1-8B-Instruct \
  llm.baseUrl=<your-vllm-url> \
  postgres.userId=<your-db-user> \
  postgres.password=<your-db-password> \
  postgres.host=<your-db-host> \
  postgres.port=5432 \
  postgres.database=<your-db-name>
```

#### Option 2: Llama Stack Mode

This mode leverages OpenShift AI's Llama Stack operator for agent orchestration.

**Prerequisites**:
- OpenShift AI 3.2+ installed on cluster
- vLLM model deployed with function calling support:
  ```
  --enable-auto-tool-choice --tool-call-parser llama3_json
  ```

**Deploy**:
```bash
make install NAMESPACE=$NAMESPACE \
  PROVIDER_MODE=llama_stack \
  postgres.userId=<your-db-user> \
  postgres.password=<your-db-password> \
  postgres.host=<your-db-host> \
  postgres.port=5432 \
  postgres.database=<your-db-name>
```

This automatically deploys:
- LlamaStackDistribution custom resource
- MCP server with SSE transport
- Copilot backend configured for Llama Stack
- Web UI

### Verify Deployment

1. **Check Pod Status**:
   ```bash
   oc get pods -n $NAMESPACE
   ```

   Expected pods:
   - `copilot-ui-*` - Web interface
   - `copilot-backend-*` - FastAPI backend
   - `pg-airman-mcp-*` - MCP server
   - `copilot-llama-stack-*` (Llama Stack mode) or `nvidia-nemotron-*` (MCP-Direct mode)

2. **Access the UI**:
   ```bash
   oc get route copilot-ui -n $NAMESPACE -o jsonpath='{.spec.host}'
   ```

   Open the URL in your browser.

3. **Test the Application**:
   - Navigate to the web interface
   - Try a sample query: "List all tables in the database"
   - Verify you see streaming responses with tool calls and results

### Configuration Options

The Makefile supports several configuration parameters:

```bash
# Provider mode
PROVIDER_MODE=mcp_direct        # or llama_stack

# Model deployment (MCP-Direct mode only)
DEPLOY_MODEL=true               # Deploy Nemotron model
llm.model=<model-name>          # Model identifier
llm.baseUrl=<vllm-url>          # External vLLM endpoint

# Llama Stack configuration (Llama Stack mode only)
llamaStack.model=<model-id>     # Model ID in vllm-inference/<name> format

# Database credentials
postgres.userId=<username>
postgres.password=<password>
postgres.host=<hostname>
postgres.port=5432
postgres.database=<db-name>

# Tool call format (MCP-Direct mode, optional)
llm.toolCallFormat=auto         # auto, nemotron, or openai
```

### Troubleshooting

**GPU Scheduling Issues**:
If pods fail to schedule due to GPU taints, verify the tolerations in `helm/nemotron-model/templates/inferenceservice.yaml`.

**MCP Connection Errors**:
- MCP-Direct mode: Check that `pg-airman-mcp` service uses streamable-http transport
- Llama Stack mode: Check that `pg-airman-mcp` service uses SSE transport (`/sse` endpoint)

**Tool Calling Failures (Llama Stack mode)**:
Verify vLLM has the required flags:
```bash
oc logs <vllm-pod> | grep "enable-auto-tool-choice"
```

**Model Not Found**:
Ensure the model name includes the provider prefix for Llama Stack mode:
- Correct: `vllm-inference/redhataillama-31-8b-instruct`
- Incorrect: `redhataillama-31-8b-instruct`

## Delete

To remove the Data Governance Co-Pilot and all associated resources:

```bash
make uninstall NAMESPACE=$NAMESPACE
```

CRITICAL: This will delete everything in the namespace and remove the namespace:
- All application deployments (UI, backend, MCP server)
- LlamaStackDistribution (if deployed)
- Model deployments (if deployed with `DEPLOY_MODEL=true`)
- Routes and services
- Secrets and ConfigMaps

## Tags

### Industry
- Technology
- Financial Services
- Healthcare
- Retail

### Use Case
- Data Governance
- Database Administration
- Compliance Automation
- Policy Enforcement

### Technology
- LLM
- RAG
- Agentic AI
- Model Context Protocol (MCP)
- vLLM
- Llama Stack
- OpenShift AI

## Reference

### Related Documentation

- [Model Context Protocol (MCP) Specification](https://modelcontextprotocol.io)
- [OpenShift AI Documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed)
- [Llama Stack Documentation](https://llama-stack.readthedocs.io)
- [vLLM Documentation](https://docs.vllm.ai)

### Architecture Details

For detailed implementation plans and architecture decisions, see:
- [Implementation Plan](/.claude/plans/fluttering-coalescing-falcon.md) - Dual-mode provider architecture
- [Testing Notebook](/notebooks/test_llama_stack.ipynb) - Llama Stack validation

### Model Requirements

**MCP-Direct Mode**:
- Nemotron models: Custom `<TOOLCALL>` tag format (auto-detected)
- Llama 3.1 models: Standard OpenAI function calling (requires vLLM flags)

**Llama Stack Mode**:
- Requires models with standard OpenAI function calling support
- vLLM must be deployed with: `--enable-auto-tool-choice --tool-call-parser llama3_json` (automatically set by this deployment)
- Nemotron custom format is NOT compatible with Llama Stack agents

### Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### License

This project is licensed under the Apache License 2.0 - see [LICENSE](LICENSE) for details.
