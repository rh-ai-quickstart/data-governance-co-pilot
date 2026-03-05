# Data Governance Co-Pilot

Empower data analysts using AI-driven natural language queries integrated with their organization's data governance policy.

## Description

This quickstart demonstrates how to build an **agentic AI application** that bridges Large Language Models (LLMs) with your enterprise data. By utilizing **EnterpriseDB’s (EDB) pg-airman-mcp**, an open-source Model Context Protocol (MCP) server for Postgres, your agent can securely query and interact with relational databases in real time.

## Deployment Architectures

The application supports two distinct deployment modes to suit your orchestration needs:

* **Custom MCP Client Mode**: A "hands-on" approach where the copilot backend manages the agentic loop directly. It interfaces between **OpenShift AI’s** inference server and the MCP server for granular control and specialized orchestration logic.
* **Llama Stack Mode**: A streamlined approach leveraging the **OpenShift AI Llama Stack operator**. This offloads agent orchestration and tool integration to a standardized, emerging framework.

Each deployment of this quickstart supports one of these two modes

## The "Dual-Path" Advantage

Choosing a two-mode solution provides a **strategic bridge** between current stability and future innovation. This architecture offers:

1.  **Future-Proofing**: It keeps the path open for continued integration with the emerging **Llama Stack** orchestration framework as it matures.
2.  **Risk Mitigation**: It protects your solution from the "API churn" associated with Llama Stack. If a target cluster does not support the version of Llama Stack required by this quickstart (0.3.5.1+rhai0), use the MCP direct deployment mode.
3.  **Custom Flexibility**: MCP direct mode allows you to implement custom logic for complex orchestration requirements that standardized frameworks (like Llama Stack) do not support.

By supporting both orchestration modes (Llama Stack and custom MCP), this quickstart serves as an instructional aid to help you learn how to implement both approach in your application and the pros and cons associated with each.

## Data Sovereignty & Security

Both modes ensure your organization maintains full sovereignty over its AI stack. By combining **Red Hat OpenShift** and **OpenShift AI**, you retain complete control over:

* **The LLM Model**: Run private models without external API calls or third-party data exposure.
* **Inference & Compute**: Keep sensitive data processing within your own managed cluster.
* **Relational Assets**: Leverage your existing investment in Postgres while extending its utility into AI workflows without compromising security.

### Key Capabilities

- **Natural Language Database Queries**: Ask questions about database schema, policies, and data governance in plain English
- **Governance-Aware Responses**: By enabling users to upload their data governance policy to the copilot using the user interface (UI), the copilot provides built-in awareness of data classification, retention policies, and access controls. The copilot merges the domain of governance policies (which largely lives in static PDF documents and websites) with a robust and intuitive conversational analytics and visualization tool.
- **EDB's powerful pg-airman-mcp MCP server**: Data governance policies are usually provided at a high level and rarely indicate how the policies is mapped to individual data stores. This mapping usually lives in the minds of data owners. The copilot bridges this gap by enabling users to create, manager and access metadata directly attached to database objects (like tables and views). Plain English metadata may be provided to indicate which objects contain PII (Personally Identifiable Information) or which objects are vetted for specific use cases. 
- **Reasoning Generation**: When deployed with the Nemotron model and MCP direct mode, users can observe the AI agent's reasoning process as it explores the database and formulates answers. This feedback loop supports iterative refinement of your data governance policy and metadata.
- **Tool Calling via MCP**: Supports MCP interaction with pg-airman-mcp using either Streamable HTTP (in direct MCP mode) and SSE (when deployed using Llama Stack). 
- **Tool Calling Formats**: Works with Nemotron (custom tool calling format) and Qwen3-14-B (using OpenAI function calling) models
- **Dual Architecture**: Choose between backend-managed or Llama Stack-managed agentic orchestration

## Architecture

### High-Level Components

The Data Governance Co-Pilot consists of five runtime components:

1. **Web UI** (Svelte): Modern chat interface with streaming responses and reasoning visualization
2. **Backend Orchestrator** (FastAPI): Provider-based architecture supporting two orchestration modes
3. **MCP Server** (EDB's pg-airman-mcp MCP Server: PostgreSQL introspection and query tools exposed via Model Context Protocol
4. **Postgres Database**: Postgres 15 database preloaded with sample ecommerce schema and data.
5. **Copilot Llama Stack Distribution**: When deployed in Llama Stack mode, the Llama Stack distribution CRD and other resources are contained in this component. The Llama Stack CRD is managed by the OpenShift AI operator.

#### Models

LLM models may be deployed with the quickstart (by specifying DEPLOY_MODEL=true) or skipped to enable users to connect to existing models. To manage model deployment and KServe artifacts, the quickstart includes two helm charts: (1) nemotron-model and (2) qwen3-model. These charts are used by the quickstart to deploy their retrieve their respective models from Huggingface and deploy directly to your target OpenShift AI inference server.

#### Optional components

This quicktart includes two optional helm charts that deploy an in-cluster minio instance and pgadmin (to support advanced database management). Pgadmin is automatically configured to work with the deployed Postgres database. These two components are only deployed if their respect make parameters are set as follows:

For deploying minio, set these make parameters:

```
DEPLOY_MINIO=true
minio.userId=<sets the user id to authenticate to the installed minio UI and API endpoint>
minio.password=<sets the password to authenticate to the installed minio UI and API endpoint>
```

For deploying pgadmin, set these make parameters:

```
DEPLOY_PGADMIN=true
pgadmin.email=<sets the email required to login to pgadmin>
pgadmin.password=<sets the password required to login to pgadmin>
```

These two optional components are not hardened for fault tolerance and security. Use them only for experimentation or extend their configuration for production use.

### High-Level Architecture Diagram

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
                        │ HTTPS (SSE)
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              FastAPI Copilot Backend                        │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         Provider Factory (Abstracts Deployment Mode) │.  │
│  └────────────┬─────────────┬───────────────────────────┘   │
│               │             │                               │
│   ┌───────────▼──────┐  ┌──▼─────────────────┐              │
│   │ Custom MCP Client|  |     Llama Stack    │              │
│   │ Provider         │  │      Provider      │              │
│   │                  │  │                    │              │
│   │ • OpenAI Client  │  │ • Llama Stack      │              │
│   │ • MCP Client     │  │   Client           │              │
│   │ (Streamable HTTP)│  │   (SSE)            │              │
│   │ • Loop Mgmt      │  │ • Agents API       │              │
│   │ • Model Format   │  │ • Event Mapping    │              │
│   │   Detection      │  │ • Stream Relay     │              │
│   └──────┬───────────┘  └────┬───────────────┘              │
│          │                   │                              │
└──────────┼───────────────────┼──────────────────────────────┘
           │                   │
           │                   ▼
           │            ┌──────────────────┐
           │            │  Llama Stack     │
           │            │  Distribution.   │
           │            │  • Agents API    │
           │            │  • Tool Runtime  │
           │            └────┬─────────────┘
           ▼                 ▼
        ──────────────────────────────────
                 │                        │
        ┌────── ─▼───────┐         ┌──────▼─────────┐
        │  MCP Server    │         │  OpenShift AI  │
        │  (pg-airman)   │         │  Inference     │
        │                │         │  Server (vLLM) │
        │ • Schema       │         │                │
        │   introspection│         │   Nemotron or  │
        │ • Policy query │         │   Qwen3        │
        │ • Data catalog │         │                │
        └───────┬────────┘         └────────────────┘
                │
                ▼
        ┌──────────────────┐
        │    PostgreSQL    │
        │     Database     │
        └──────────────────┘
```

### Deployment Modes

#### Custom MCP Client Mode

In this mode, the FastAPI backend manages the complete agentic loop:

1. Receives natural language query from UI
2. Calls vLLM model with available tools
3. Parses model response (supports Nemotron custom tags or OpenAI function calling)
4. Executes tool calls via MCP client using Streamable HTTP
5. Continues iteration until final answer is reached
6. Streams all events (reasoning, tool calls, results) to UI using SSE
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

**Best for**: Organizations leveraging OpenShift AI infrastructure, preferring managed agent orchestration, or using standard OpenAI-compatible models. Note that Llama Stack supports both turn- and step-based inference. In this quickstart, we use it's ability to implement fire-and-forget, turn-based inference. Note that RHOAI llama stack is a preview technology and will likely change in future versions of RHOAI. This mode is not recommended for production use for version (0.3.5).

### Technology Stack

- **Frontend**: Svelte 5, TypeScript, TailwindCSS, Server-Sent Events (SSE) to communicate with Copilot Backend
- **Colpilot Backend**: Python 3.12, FastAPI
- **LLM Inference**:
  - OpenShift AI inference server using vLLM (v0.11.0)
- **Orchestration**:
  - Custom MCP Client: Supports Nemotron and Qwen3 models.
  - Llama Stack: OpenShift AI Llama Stack Operator vers. 0.3.5.1+rhai0 (works with Qwen3 model)
- **Tools**: Model Context Protocol (MCP) server for PostgreSQL (pg-airman-mcp using a custom build)
- **Database**: PostgreSQL Database (version 15)
- **Platform**: OpenShift Container Platform 4.20.14, OpenShift AI 3.2 or higher 

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

- **OpenShift AI**: Version 3.2 (make sure Llama Stack is 0.3.5.1+rhai0)
- **Llama Stack Operator**: Included with OpenShift AI 3.2 (make sure Llama Stack is 0.3.5.1+rhai0)

## Deploy

### Prerequisites

1. **Access to OpenShift Cluster**:
   ```bash
   oc login <your-cluster-url>
   ```

2. **Clone the Repository**:
   ```bash
   git clone https://github.com/your-org/data-governance-co-pilot.git
   cd data-governance-co-pilot/helm
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

5a. **Full Installation (with Llama Stack backend + Qwen3 model)**:

Note: Llama Stack mode works only with version 0.3.5.1+rhai0. It will not work with other versions.
See 4 above to learn how to return the version of Llama Stack your cluster supports.

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

In this mode, you must deploy a Qwen3-14B model and provide it's endpoint URL and model resource name in the copilot-backend/values.yaml file. Provide the apikey when invoking the make command as shown below. Also, take note of required configuration parameters for your existing model (see qwen3-model helm chart in this project).

Note: Llama Stack mode works only with version 0.3.5.1+rhai0. It will not work with other versions.
See 4 above to learn how to return the version of Llama Stack your cluster supports.

   ```bash
   make install NAMESPACE=samouelian-dev DEPLOY_MODEL=false MODEL=qwen3 \
   PROVIDER_MODE=llama_stack postgres.userId=postgres \
   postgres.password=postgres postgres.databaseName=postgres \
   llm.apiKey=xyz llm.baseUrl=https://xyz.io/v1 llm.model=qwen3-14b
   ```

5c. **Full Installation (with MCP Direct backend + Nemotron or Qwen3 model)**:

Using Nemotron model:

   ```bash
   make install NAMESPACE=your-namespace \
     PROVIDER_MODE=mcp_direct \
     DEPLOY_MODEL=true \
     MODEL=nemotron \
     postgres.userId=postgres \
     postgres.password=postgres \
     postgres.databaseName=postgres \
   ```

Using qwen3 model:

   ```bash
   make install NAMESPACE=your-namespace \
     PROVIDER_MODE=mcp_direct \
     DEPLOY_MODEL=true \
     MODEL=qwen3 \
     postgres.userId=postgres \
     postgres.password=postgres \
     postgres.databaseName=postgres \
   ```


5d. **Same as 5c above exception without the model**:

NOTE: In this mode, you must deploy a Nemotron Nano 9b model or a Qwen3-14B model and provide it's endpoint URL and model resource name in the copilot-backend/values.yaml file. Provide the apikey when invoking the make command as shown below. Also, take note of required configuration parameters for your existing model (see nemotron-model or qwen3-model helm chart in this project).

Using nemotron model:

   ```bash
   make install NAMESPACE=samouelian-dev DEPLOY_MODEL=false MODEL=nemotron \
   PROVIDER_MODE=mcp_direct postgres.userId=postgres \
   postgres.password=postgres postgres.databaseName=postgres \
   llm.apiKey=xyz llm.baseUrl=https://xyz.io/v1 llm.model=your-model-resource-name
   ```

   ```bash
   make install NAMESPACE=samouelian-dev DEPLOY_MODEL=false MODEL=qwen3 \
   PROVIDER_MODE=mcp_direct postgres.userId=postgres \
   postgres.password=postgres postgres.databaseName=postgres \
   llm.apiKey=xyz llm.baseUrl=https://xyz.io/v1 llm.model=your-model-resource-name
   ```

NOTE: There are two model parameters above. The first (MODEL=nemotron) serves as a logical identifier
that indicates which of the two models your deployment should use ('qwen3' or 'nemotron'). One of these two values must be provided exactly as shown. The second parameter (llm.model=your-model-resource-name) is the deployed resource name of your model (e.g., nvidia-nemotron-nano-9b-v2). This value should represent whatever you've chosen for your model deployment. If DEPLOY_MODEL=true, this value is set automatically.

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
See the Optional components section above for additional parameters needed to deploy optional components.

**GPU Scheduling Issues**:
If pods fail to schedule due to GPU taints:
```bash
# Check node taints
oc describe node <gpu-node-name> | grep Taints

# Verify tolerations match in helm chart templates:
# - helm/nemotron-model/templates/inferenceservice.yaml
# - helm/qwen3-model/templates/inferenceservice.yaml
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
- Nemotron's tool calling format is not tested with Llama Stack agent
- The Makefile includes validation to prevent invalid model/mode combinations
- Tool call format is auto-detected in Custom MCP Client mode

### Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### License

This project is licensed under the Apache License 2.0 - see [LICENSE](LICENSE) for details.
