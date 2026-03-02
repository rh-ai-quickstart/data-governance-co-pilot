# Data Governance Copilot - Deployment Modes

This document describes the flexible deployment options for the Data Governance Copilot application.

## Overview

The application supports two LLM provider modes and two model options, with the flexibility to either deploy models to your cluster or use external model endpoints.

## Provider Modes

### 1. MCP-Direct Mode (`PROVIDER_MODE=mcp_direct`)
- Backend connects directly to vLLM model via OpenAI-compatible API
- Backend manages complete agentic loop (tool calling iterations)
- Supports both Nemotron and Qwen3 models
- Recommended for: Maximum control over tool calling behavior

### 2. Llama Stack Mode (`PROVIDER_MODE=llama_stack`)
- Backend uses Llama Stack Agents API
- Llama Stack manages agentic loop internally
- **Only compatible with Qwen3** (OpenAI function calling format)
- Recommended for: Simplified deployment, Llama Stack ecosystem integration

## Model Options

### NVIDIA Nemotron Nano 9B v2
- **Size**: 9 billion parameters
- **Tool Calling**: Custom `<TOOLCALL>` tag format (Mistral parser)
- **Compatible Modes**: MCP-Direct only
- **Resource Requirements**: 1 GPU, 10Gi RAM
- **Source**: quay.io/eformat/nvidia-nemotron-nano-9b-v2 (OCI) or HuggingFace

### Qwen3-14B
- **Size**: 14 billion parameters
- **Tool Calling**: OpenAI function calling format (Hermes parser)
- **Compatible Modes**: Both MCP-Direct and Llama Stack
- **Resource Requirements**: 1 GPU, 24Gi RAM
- **Source**: HuggingFace hf://Qwen/Qwen3-14B (public, no token needed)

## Deployment Scenarios

### Scenario 1: Deploy Nemotron Model + MCP-Direct Mode

Deploy Nemotron to your cluster and configure the backend to use it.

```bash
make install NAMESPACE=myns \
  MODEL=nemotron \
  DEPLOY_MODEL=true \
  PROVIDER_MODE=mcp_direct \
  postgres.userId=admin \
  postgres.password=<password> \
  postgres.databaseName=adventure_works \
  minio.userId=admin \
  minio.password=<password> \
  pgadmin.email=admin@example.com \
  pgadmin.password=<password>
```

**What happens:**
1. Nemotron model deployed via KServe InferenceService
2. Model pulled from OCI image or HuggingFace
3. Backend auto-configured with model endpoint and API key
4. MCP tools available for database operations

### Scenario 2: Deploy Qwen3 Model + MCP-Direct Mode

Deploy Qwen3 to your cluster for local inference.

```bash
make install NAMESPACE=myns \
  MODEL=qwen3 \
  DEPLOY_MODEL=true \
  PROVIDER_MODE=mcp_direct \
  postgres.userId=admin \
  postgres.password=<password> \
  postgres.databaseName=adventure_works \
  minio.userId=admin \
  minio.password=<password> \
  pgadmin.email=admin@example.com \
  pgadmin.password=<password>
```

**What happens:**
1. Qwen3-14B model deployed via KServe InferenceService
2. Model pulled from HuggingFace (public, no token needed)
3. Backend auto-configured with model endpoint and API key
4. MCP tools available for database operations

### Scenario 3: Deploy Qwen3 Model + Llama Stack Mode

Deploy Qwen3 and use Llama Stack for agentic orchestration.

```bash
make install NAMESPACE=myns \
  MODEL=qwen3 \
  DEPLOY_MODEL=true \
  PROVIDER_MODE=llama_stack \
  postgres.userId=admin \
  postgres.password=<password> \
  postgres.databaseName=adventure_works \
  minio.userId=admin \
  minio.password=<password> \
  pgadmin.email=admin@example.com \
  pgadmin.password=<password>
```

**What happens:**
1. Qwen3-14B model deployed via KServe InferenceService
2. Llama Stack deployed and configured to use the Qwen3 model
3. Backend auto-configured to use Llama Stack Agents API
4. MCP tools registered as Llama Stack toolgroup

### Scenario 4: Use External Nemotron + MCP-Direct Mode

Use an existing Nemotron deployment (e.g., vLLM server on another cluster).

```bash
make install NAMESPACE=myns \
  MODEL=nemotron \
  DEPLOY_MODEL=false \
  PROVIDER_MODE=mcp_direct \
  copilot.llmBaseUrl=https://your-nemotron-endpoint/v1 \
  copilot.llmModel=nvidia-nemotron-nano-9b-v2 \
  copilot.llmApiKey=your-api-key \
  postgres.userId=admin \
  postgres.password=<password> \
  postgres.databaseName=adventure_works \
  minio.userId=admin \
  minio.password=<password> \
  pgadmin.email=admin@example.com \
  pgadmin.password=<password>
```

**What happens:**
1. No model deployed to cluster
2. Backend configured to use external Nemotron endpoint
3. MCP tools available for database operations

### Scenario 5: Use External Qwen3 (LiteLLM) + Llama Stack Mode

Use an existing Qwen3 deployment via LiteLLM proxy.

```bash
make install NAMESPACE=myns \
  MODEL=qwen3 \
  DEPLOY_MODEL=false \
  PROVIDER_MODE=llama_stack \
  copilot.llmModel=qwen3-14b \
  copilot.llmBaseUrl=https://litellm-prod.apps.maas.redhatworkshops.io/v1 \
  copilot.llmApiKey=sk-your-api-key \
  postgres.userId=admin \
  postgres.password=<password> \
  postgres.databaseName=adventure_works \
  minio.userId=admin \
  minio.password=<password> \
  pgadmin.email=admin@example.com \
  pgadmin.password=<password>
```

**What happens:**
1. No model deployed to cluster
2. Llama Stack deployed and configured to use external LiteLLM endpoint
3. Backend configured to use Llama Stack Agents API
4. MCP tools registered as Llama Stack toolgroup

### Scenario 6: Use External Qwen3 + MCP-Direct Mode

Use an existing Qwen3 vLLM deployment with direct backend connection.

```bash
make install NAMESPACE=myns \
  MODEL=qwen3 \
  DEPLOY_MODEL=false \
  PROVIDER_MODE=mcp_direct \
  copilot.llmBaseUrl=https://your-qwen3-endpoint/v1 \
  copilot.llmModel=qwen3-14b \
  copilot.llmApiKey=your-api-key \
  postgres.userId=admin \
  postgres.password=<password> \
  postgres.databaseName=adventure_works \
  minio.userId=admin \
  minio.password=<password> \
  pgadmin.email=admin@example.com \
  pgadmin.password=<password>
```

**What happens:**
1. No model deployed to cluster
2. Backend configured to use external Qwen3 endpoint directly
3. MCP tools available for database operations

## Model-Specific Deployment

You can also deploy individual models separately:

### Deploy Nemotron Model Only
```bash
make nemotron-model-install NAMESPACE=myns
```

### Deploy Qwen3 Model Only
```bash
make qwen3-model-install NAMESPACE=myns
```

## Configuration Parameters

### Required Parameters
- `NAMESPACE` - OpenShift namespace
- `postgres.userId` - PostgreSQL username
- `postgres.password` - PostgreSQL password
- `postgres.databaseName` - PostgreSQL database name
- `minio.userId` - MinIO username (min 3 characters)
- `minio.password` - MinIO password (min 8 characters)
- `pgadmin.email` - pgAdmin login email
- `pgadmin.password` - pgAdmin password

### Optional Parameters
- `MODEL` - Model to use: `nemotron` or `qwen3` (default: `qwen3`)
- `DEPLOY_MODEL` - Deploy model to cluster: `true` or `false` (default: `false`)
- `PROVIDER_MODE` - Provider mode: `mcp_direct` or `llama_stack` (default: `mcp_direct`)
- `copilot.llmBaseUrl` - External LLM endpoint URL (required if `DEPLOY_MODEL=false`)
- `copilot.llmModel` - External LLM model name (required if `DEPLOY_MODEL=false`)
- `copilot.llmApiKey` - LLM API key (use `not-needed` for unauthenticated vLLM)
- `copilot.maxContextLength` - Max context length in tokens (default: 32768)
- `model.storage.uri` - Custom model URI (overrides default)
- `model.storage.s3Bucket` - S3 bucket path for model storage

## Compatibility Matrix

| Model | MCP-Direct | Llama Stack | Tool Calling Format | Notes |
|-------|-----------|-------------|-------------------|-------|
| Nemotron 9B | ✅ Yes | ❌ No | Custom `<TOOLCALL>` tags | Incompatible with Llama Stack |
| Qwen3-14B | ✅ Yes | ✅ Yes | OpenAI function calling | Recommended for Llama Stack |

## Resource Requirements

### Nemotron Model Deployment
- GPU: 1x NVIDIA GPU
- CPU: 4-8 cores
- Memory: 8-10Gi
- Storage: ~20GB for model weights

### Qwen3 Model Deployment
- GPU: 1x NVIDIA GPU
- CPU: 4-8 cores
- Memory: 20-24Gi
- Storage: ~30GB for model weights

### Application Components (No Model)
- CPU: 2-4 cores total
- Memory: 4-6Gi total
- Storage: 20GB PVCs

## vLLM Configuration

### Nemotron vLLM Parameters
```yaml
--enable-auto-tool-choice
--tool-call-parser mistral
--max-model-len 32768
--gpu-memory-utilization 0.95
```

### Qwen3 vLLM Parameters
```yaml
--enable-auto-tool-choice
--tool-call-parser hermes
--reasoning-parser qwen3
--max-model-len 32768
--gpu-memory-utilization 0.95
```

## Monitoring Deployment

### Check Model Status
```bash
# Nemotron
oc get inferenceservice nvidia-nemotron-nano-9b-v2 -n <namespace> -w

# Qwen3
oc get inferenceservice qwen3-14b -n <namespace> -w
```

### Get Model Endpoint
```bash
# Nemotron
oc get route nvidia-nemotron-nano-9b-v2 -n <namespace>

# Qwen3
oc get route qwen3-14b -n <namespace>
```

### Check Llama Stack Status
```bash
oc get llamastackdistribution copilot-llama-stack -n <namespace>
```

## Troubleshooting

### Nemotron Incompatible with Llama Stack

**Error**: "Nemotron model is not compatible with Llama Stack mode."

**Solution**: Use `PROVIDER_MODE=mcp_direct` with Nemotron, or switch to Qwen3 for Llama Stack mode.

### Model Not Scheduling

**Error**: Pods stuck in Pending state

**Cause**: No available GPU nodes or insufficient resources

**Solution**:
- Check GPU node availability: `oc get nodes -l nvidia.com/gpu=true`
- Review pod events: `oc describe pod <pod-name> -n <namespace>`
- Adjust resource requests in model values.yaml

### Out of Memory During Model Load

**Error**: Pod crashes with OOM error

**Cause**: Insufficient GPU memory for model size

**Solution**:
- Reduce `--max-model-len` in model values.yaml
- Reduce `--gpu-memory-utilization` (try 0.85 or 0.8)
- Use smaller model or more powerful GPU

## References

- [vLLM Tool Calling Documentation](https://docs.vllm.ai/en/latest/features/tool_calling/)
- [Qwen3 vLLM Guide](https://docs.vllm.ai/projects/recipes/en/latest/Qwen/Qwen3.5.html)
- [Llama Stack Documentation](https://llama-stack.readthedocs.io/)
- [KServe Documentation](https://kserve.github.io/website/)
