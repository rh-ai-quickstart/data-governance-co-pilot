# Data Governance Co-Pilot

Empower data analysts using AI-driven natural language queries integrated with their organization's data governance policy.

## Description

This quickstart demonstrates how to build an **agentic AI application** that bridges Large Language Models (LLMs) with your enterprise data. By utilizing **EnterpriseDB’s (EDB) pg-airman-mcp**, an open-source Model Context Protocol (MCP) server for Postgres, your agent can securely query and interact with relational databases in real time.

## Deployment Architectures

The application supports two distinct deployment modes to suit your orchestration needs:

* **Custom MCP Client Mode**: A "hands-on" approach where the backend manages the agentic loop directly. It interfaces between **OpenShift AI’s** inference server and the MCP server for granular control and specialized orchestration logic.
* **Llama Stack Mode**: A streamlined approach leveraging the **OpenShift AI Llama Stack operator**. This offloads agent orchestration and tool integration to a standardized, emerging framework.

## The "Dual-Path" Advantage

Choosing a two-mode solution provides a **strategic bridge** between current stability and future innovation. This architecture offers:

1.  **Future-Proofing**: It keeps the path open for continued integration with the emerging **Llama Stack** orchestration framework as it matures.
2.  **Risk Mitigation**: It protects your solution from the "API churn" associated with rapidly changing experimental frameworks.
3.  **Custom Flexibility**: It allows you to implement custom logic for complex orchestration requirements that standardized frameworks may not yet support.

## Data Sovereignty & Security

Both modes ensure your organization maintains full sovereignty over its AI stack. By combining **Red Hat OpenShift** and **OpenShift AI**, you retain complete control over:

* **The LLM Model**: Run private models without external API calls or third-party data exposure.
* **Inference & Compute**: Keep sensitive data processing within your own managed cluster.
* **Relational Assets**: Leverage your existing investment in Postgres while extending its utility into AI workflows without compromising security.

### Key Capabilities

- **Natural Language Database Queries**: Ask questions about database schema, policies, and data governance in plain English
- **Governance-Aware Responses**: Built-in awareness of data classification, retention policies, and access controls
- **Real-Time Streaming**: Watch the AI agent's reasoning process as it explores the database and formulates answers (the Llama Stack deployment route may provide limited reasoning output)
- **Tool Calling via MCP**: Database operations executed through the Model Context Protocol for secure, structured interactions
- **Multi-Model Support**: Works with Nemotron (custom tool calling format) and Qwen3-14-B (using OpenAI function calling) models
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
│   │ Custom MCP Client|  |     Llama Stack    │              │
│   │ Provider         │  │      Provider      │              │
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
│ LLM Models:      │   │  Llama Stack     │
│ • Nemotron       │   │  (OpenShift AI)  │
│ • Qwen3-14B      │   │  • Agents API    │
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
        │    PostgreSQL    │
        │     Database     │
        └──────────────────┘
```

### Architecture Modes

#### Custom MCP Client Mode

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

**Best for**: Organizations leveraging OpenShift AI infrastructure, preferring managed agent orchestration, or using standard OpenAI-compatible models. Note that Llama Stack supports both turn- and step-based inference. In this quickstart, we use it's ability to implement fire-and-forget, turn-based inference. Note that RHOAI llama stack is a preview technology and will likely change in future versions of RHOAI.

### Technology Stack

- **Frontend**: Svelte 5, TypeScript, TailwindCSS, Server-Sent Events (SSE)
- **Backend**: Python 3.12, FastAPI, OpenAI Python SDK, MCP SDK
- **LLM Inference**:
  - Custom MCP Client: vLLM (supports Nemotron (MCP Direct Mode), Qwen3 (Llama Stack Mode))
  - Llama Stack: OpenShift AI Llama Stack Operator
- **Tool Runtime**: Model Context Protocol (MCP) server for PostgreSQL (pg-airman-mcp)
- **Database**: PostgreSQL Database
- **Platform**: OpenShift Container Platform 4.20.14

## Requirements

### Minimum Hardware Requirements

- **OpenShift Cluster**: 3+ worker nodes
- **GPU Nodes**: At least 1 node with NVIDIA GPU (for LLM inference)
  - Recommended: NVIDIA A100, A10, or L40 (24GB+ VRAM)
  - Minimum: NVIDIA T4 (16GB VRAM)
- **Memory**: 32GB RAM per worker node (minimum)
- **Storage**: 100GB persistent storage for model weights and application data

### Minimum Software Requirements

- **OpenShift Container Platform**: Version 4.20.14 or higher with llama stack preview enabled
- **NVIDIA GPU Operator**: For GPU support on OpenShift
- **Helm**: Version 3.8 or higher
- **oc CLI**: OpenShift command-line tool (matching cluster version)
- **PostgreSQL Database**: Version 12 or higher
  - Can be deployed as part of this quickstart or use existing instance
  - Database credentials required for deployment

### Requirements (Llama Stack Mode)

- **OpenShift AI**: Version 3.2 
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

3. **Enable llama stack support in OpenShift AI if using the llama_stack PROVIDER_MODE (see below)**

See Activating the Llama Stack Operator here: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.0/html/working_with_llama_stack/activating-the-llama-stack-operator_rag

4. **This quickstart was tested using OpenShift 4.20.14 and the Red Hat Build of Llama Stack (0.3.5.1+rhai0) with the CRD
API at llamastack.io/v1alpha1. To check the version of Llama Stack in your cluster, use these commands:

Get API Version of the Red Hat Llama Stack Distribution CRD (Custom Resource Definition):
   ```bash
   oc get llamastackdistribution copilot-llama-stack -n samouelian-dev -o jsonpath='{.apiVersion}'
   ```

Get the Llama Stack version in your cluster:

   ```bash
   oc get datasciencecluster default-dsc -o json | jq -r '.status.components.llamastackoperator.releases[] | select(.name == \
   "Llama Stack") | .version'
   ```

5. The installation of this quickstart requires the make utility and supports multiple deployment modes. 

IMPORTANT: In this initial release, only the first two models below are fully tested. This mode uses the Llama Stack distribution within OpenShift AI with either a new deployment of the Qwen3 model or an existing deployment you'd prefer to use. 

5a. **Full Installation (with Llama Stack backend + Qwen3 model)**:
   ```bash
   make install NAMESPACE=your-namespace \
     DEPLOY_MODEL=true \
     MODEL=qwen3 \
     PROVIDER_MODE=llama_stack \
     postgres.userId=postgres \
     postgres.password=postgres \
     postgres.databaseName=postgres
   ```

5b. **Same as 5a above except without the model**:

NOTE: In this mode, you must deploy a Qwen3-14B model and provide it's endpoint URL and model resource name
in the copilot-backend/values.yaml file. Provide the apikey when invoking the make command as shown below. Also, take
note of required configuration parameters for your existing model (see qwen3-model helm chart in this project).

   ```bash
   make install NAMESPACE=samouelian-dev DEPLOY_MODEL=false MODEL=qwen3 \
   PROVIDER_MODE=llama_stack postgres.userId=postgres \
   postgres.password=postgres postgres.databaseName=postgres \
   llm.apiKey=xyz llm.baseUrl=https://xyz.io/v1 llm.model=qwen3-14b
   ```

5c. **Full Installation (with MCP Direct backend + Nemotron model)**:
   ```bash
   make install NAMESPACE=your-namespace \
     PROVIDER_MODE=mcp_direct \
     DEPLOY_MODEL=true \
     MODEL=nemotron \
     postgres.userId=postgres \
     postgres.password=postgres \
     postgres.databaseName=postgres \
   ```

5d. **Same as 5c above exception without the model**:

NOTE: In this mode, you must deploy a Nemotron Nano 9b model and provide it's endpoint URL and model resource name
in the copilot-backend/values.yaml file. Provide the apikey when invoking the make command as shown below. Also, take
note of required configuration parameters for your existing model (see nemotron-model helm chart in this project).

   ```bash
   make install NAMESPACE=samouelian-dev DEPLOY_MODEL=false MODEL=nemotron \
   PROVIDER_MODE=mcp_direct postgres.userId=postgres \
   postgres.password=postgres postgres.databaseName=postgres \
   llm.apiKey=xyz llm.baseUrl=https://xyz.io/v1 llm.model=your-model-resource-name
   ```

NOTE: There are two model parameters above. The first (MODEL=nemotron) serves as a logical identifier
that indicates which of the two models your deployment should use ('qwen3' or 'nemotron'). One of these two values
must be provided exactly as shown. The second parameter (llm.model=your-model-resource-name) is the deployed resource name
of your model (e.g., nvidia-nemotron-nano-9b-v2). This value should represent whatever you've chosen for your model deployment. If DEPLOY_MODEL=true, this value is set automatically.

### Post Deployment

1. **Login to the Data Governance Copilot**:

Once your make installation completes, a URL is shown. Point your browser to this URL to start using the data governance copilot. You can also retrieve the URL using this command:

   ```bash
   oc get route copilot-ui -n $NAMESPACE -o jsonpath='{.spec.host}'
   ```
2. **Test the Application**:
   - Navigate to the web interface
   - Try a sample query: "List all tables in the database"
   - Verify you see streaming responses with tool calls and results

### Configuration Options

The Makefile supports several configuration parameters:

```bash
# Provider mode
PROVIDER_MODE=mcp_direct        # Options: mcp_direct (default), llama_stack

# Model selection and deployment
MODEL=nemotron                  # Options: nemotron (default), qwen3 (NOTE: Use qwen3 with llama_stack mode and nemotron with mcp_direct)
DEPLOY_MODEL=true               # Options: true (auto-deploy), false (use existing)

# Model deployment options (when DEPLOY_MODEL=false)
llm.model=<model-name>          # Model identifier for Custom MCP Client mode
llm.baseUrl=<vllm-url>          # External vLLM endpoint for Custom MCP Client mode
llm.apiKey=<api-key>     # API key for external vLLM

# Database credentials
postgres.userId=<username>
postgres.password=<password>
postgres.databaseName=<db-name>
postgres.host=<hostname>        # Optional, defaults to deployed PostgreSQL
postgres.port=5432              # Optional

# Tool call format (Custom MCP Client mode, optional)
llm.toolCallFormat=auto         # Options: auto (default), nemotron, openai
                                # auto: detects from model name
```

**GPU Scheduling Issues**:
If pods fail to schedule due to GPU taints:
```bash
# Check node taints
oc describe node <gpu-node-name> | grep Taints

# Verify tolerations match in helm chart templates:
# - helm/nemotron-model/templates/inferenceservice.yaml
# - helm/llama-model/templates/inferenceservice.yaml
```
## Delete

To remove the Data Governance Co-Pilot and all associated resources:

```bash
make uninstall NAMESPACE=$NAMESPACE
```

CRITICAL: This will delete everything in the namespace and remove the namespace:
- All application deployments (UI, backend, MCP server)
- LlamaStackDistribution (if deployed)
- Model deployments (nemotron or qwen3, if deployed with `DEPLOY_MODEL=true`)
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

### Model Requirements

This deployment supports two LLM models, each with different characteristics:

**Nemotron Model** (hf://nvidia/NVIDIA-Nemotron-Nano-9B-v2):
- **Tool Calling Format**: Custom `<TOOLCALL>` tag format
- **Authentication**: None required (publicly available on HuggingFace)
- **Compatible Modes**: Custom MCP Client mode only
- **vLLM Flags**: See nemotron helm chart in this project

**Qwen3 Model** (hf://Qwen/Qwen3-14B-AWQ):
- **Tool Calling Format**: Standard OpenAI function calling
- **Compatible Modes**: Both Custom MCP Client and Llama Stack modes
- **vLLM Flags**: See qwen3 helm chart in this project

**Key Compatibility Notes**:
- Llama Stack mode tested using
- Nemotron's tool calling format is not tested with Llama Stack agent
- The Makefile includes validation to prevent invalid model/mode combinations
- Tool call format is auto-detected in Custom MCP Client mode

### Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### License

This project is licensed under the Apache License 2.0 - see [LICENSE](LICENSE) for details.
