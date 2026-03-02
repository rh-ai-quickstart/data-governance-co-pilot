# Qwen3-14B Model Deployment

This Helm chart deploys the Qwen3-14B model using KServe on OpenShift AI with vLLM serving runtime.

## Features

- **Tool Calling Support**: Configured with Hermes tool-call-parser for function calling capabilities
- **Reasoning Support**: Includes Qwen3 reasoning parser for enhanced reasoning capabilities
- **GPU Acceleration**: Optimized for NVIDIA GPU deployment
- **OAuth Protection**: Optional OAuth proxy for secure access
- **OpenShift Routes**: Automatic route creation with configurable timeouts

## Prerequisites

- OpenShift AI platform with KServe installed
- GPU nodes with NVIDIA drivers
- Sufficient GPU memory (recommended: 24GB+ VRAM for Qwen3-14B)

## Installation

### Deploy via Makefile (Recommended)

From the project root:

```bash
make qwen3-model-install NAMESPACE=your-namespace
```

### Deploy via Helm directly

```bash
helm install qwen3-model ./qwen3-model -n your-namespace
```

## Configuration

### Model Storage

The chart supports three storage backends:

1. **Hugging Face (default)**: Automatically downloads from HuggingFace
   ```yaml
   model:
     storage:
       type: uri
       uri: "hf://Qwen/Qwen3-14B"
   ```

2. **S3**: Load from S3-compatible storage
   ```yaml
   model:
     storage:
       type: s3
       s3Bucket: "s3://my-bucket/qwen3-14b/"
   ```

3. **PVC**: Load from existing PersistentVolumeClaim
   ```yaml
   model:
     storage:
       type: pvc
       pvcName: "qwen3-model-pvc"
   ```

### vLLM Tool Calling Configuration

The model is configured with the following vLLM parameters for tool calling:

```yaml
model:
  runtime:
    args:
      - --enable-auto-tool-choice      # Enable automatic tool selection
      - --tool-call-parser             # Tool calling format
      - hermes                          # Use Hermes parser for Qwen3
      - --reasoning-parser             # Reasoning capability
      - qwen3                           # Qwen3-specific reasoning
```

**Note**: The `hermes` tool-call-parser is compatible with Qwen3 models and enables function calling via the OpenAI-compatible API.

### Resource Configuration

Default resources are optimized for Qwen3-14B:

```yaml
model:
  resources:
    limits:
      nvidia.com/gpu: 1
      cpu: "8"
      memory: "24Gi"
    requests:
      nvidia.com/gpu: 1
      cpu: "4"
      memory: "20Gi"
```

Adjust based on your cluster capacity and model requirements.

### Security

OAuth authentication can be enabled/disabled:

```yaml
security:
  enableAuth: true  # Enable OAuth proxy
```

## Accessing the Model

After deployment, the model will be available:

- **Internal**: `http://qwen3-14b-predictor.your-namespace.svc.cluster.local/v1`
- **External**: Via the created OpenShift route (if enabled)

Get the route URL:

```bash
oc get route -n your-namespace | grep qwen3-14b
```

## Tool Calling Usage

The deployed model supports OpenAI-compatible tool calling:

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://your-model-route/v1",
    api_key="not-needed"
)

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get weather for a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string"}
                },
                "required": ["location"]
            }
        }
    }
]

response = client.chat.completions.create(
    model="qwen3-14b",
    messages=[{"role": "user", "content": "What's the weather in Paris?"}],
    tools=tools,
    tool_choice="auto"
)
```

## Troubleshooting

### Pod not scheduling

Check GPU node taints and tolerations in the InferenceService spec.

### Out of memory errors

Reduce `--max-model-len` or `--gpu-memory-utilization` in `values.yaml`:

```yaml
model:
  runtime:
    args:
      - --max-model-len=16384        # Reduce context length
      - --gpu-memory-utilization
      - "0.85"                        # Reduce GPU memory usage
```

### Tool calling not working

Ensure you're using the OpenAI-compatible `/v1/chat/completions` endpoint and passing `tools` in the request.

## References

- [vLLM Tool Calling Documentation](https://docs.vllm.ai/en/latest/features/tool_calling/)
- [Qwen3 Usage Guide](https://docs.vllm.ai/projects/recipes/en/latest/Qwen/Qwen3.5.html)
- [Qwen3-14B Model Card](https://huggingface.co/Qwen/Qwen3-14B)
