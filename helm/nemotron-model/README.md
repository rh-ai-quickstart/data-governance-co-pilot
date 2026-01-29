# NVIDIA Nemotron Nano 9B v2 Model Deployment

This Helm chart deploys the NVIDIA Nemotron Nano 9B v2 language model using KServe on OpenShift AI.

## Features

- **Automatic model deployment** using KServe InferenceService
- **OCI container image** default storage (no S3 configuration required)
- **vLLM runtime** for efficient LLM serving
- **OAuth authentication** via oauth-proxy sidecar
- **Extended timeouts** for long-running inference requests (10 minutes)
- **GPU acceleration** with NVIDIA GPU support
- **Flexible storage** options (OCI image, S3, PVC, or direct URI)

## Prerequisites

- OpenShift 4.17+ cluster
- Red Hat OpenShift AI operator installed
- NVIDIA GPU operator installed (for GPU nodes)
- No additional storage configuration required (uses OCI container image by default)

## Model Storage

The model is deployed using an OCI container image by default. No additional storage configuration is required.

### Option 1: OCI Container Image (Default - Recommended)
```yaml
model:
  storage:
    type: uri
    uri: "oci://quay.io/eformat/nvidia-nemotron-nano-9b-v2"
```

**This is the default configuration - no changes needed!**

### Option 2: S3 Storage
```yaml
model:
  storage:
    type: s3
    s3Bucket: "s3://your-bucket/NVIDIA-Nemotron-Nano-9B-v2"
```

### Option 3: PVC Storage
```yaml
model:
  storage:
    type: pvc
    pvcName: "model-storage-pvc"
```

### Option 4: Custom URI
```yaml
model:
  storage:
    type: uri
    uri: "https://your-model-server.com/model"
```

## Installation

### Manual Installation

```bash
# Install with default OCI container image (recommended)
helm install nemotron-model ./nemotron-model \
  --namespace my-namespace

# Or install with custom S3 storage
helm install nemotron-model ./nemotron-model \
  --namespace my-namespace \
  --set model.storage.type=s3 \
  --set model.storage.s3Bucket=s3://my-bucket/NVIDIA-Nemotron-Nano-9B-v2
```

### Makefile Installation

```bash
# Standalone model deployment (uses OCI image by default)
make nemotron-model-install NAMESPACE=my-namespace

# Or as part of full stack deployment
make install \
  NAMESPACE=my-namespace \
  DEPLOY_MODEL=true \
  postgres.userId=postgres \
  postgres.password=password \
  postgres.databaseName=mydb \
  minio.userId=minio \
  minio.password=minio123 \
  pgadmin.email=admin@example.com \
  pgadmin.password=admin123
```

## Configuration

### Key Configuration Options

| Parameter | Description | Default |
|-----------|-------------|---------|
| `model.name` | InferenceService name | `nvidia-nemotron-nano-9b-v2` |
| `model.storage.type` | Storage type (uri, s3, pvc) | `uri` |
| `model.storage.uri` | OCI image or URI path | `oci://quay.io/eformat/nvidia-nemotron-nano-9b-v2` |
| `model.storage.s3Bucket` | S3 bucket path (optional) | `""` |
| `model.resources.limits.nvidia.com/gpu` | Number of GPUs | `1` |
| `model.resources.limits.memory` | Memory limit | `10Gi` |
| `route.timeout` | Route timeout for inference | `600s` (10 min) |
| `route.oauthProxyUpstreamTimeout` | OAuth proxy upstream timeout | `10m` |
| `security.enableAuth` | Enable OAuth authentication | `true` |

### Advanced Runtime Configuration

The vLLM runtime can be configured with additional arguments:

```yaml
model:
  runtime:
    args:
      - --max-model-len=32768
      - --task=generate
      - --trust_remote_code
      - --gpu-memory-utilization=0.95
      - --tool-call-parser=mistral
      - --enable-auto-tool-choice
```

## Accessing the Model

### Get the Model Endpoint

```bash
# Get the external route URL
oc get route nvidia-nemotron-nano-9b-v2 -n my-namespace -o jsonpath='{.spec.host}'
```

### Get the Authentication Token

```bash
# Get the service account token
oc sa get-token default -n my-namespace
```

### Test the Model

```bash
# Test with a simple completion request
curl -X POST https://$(oc get route nvidia-nemotron-nano-9b-v2 -n my-namespace -o jsonpath='{.spec.host}')/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $(oc sa get-token default -n my-namespace)" \
  -d '{
    "model": "nvidia-nemotron-nano-9b-v2",
    "messages": [{"role": "user", "content": "Hello! Who are you?"}],
    "max_tokens": 100
  }'
```

## Monitoring

### Check InferenceService Status

```bash
# Watch the deployment progress
oc get inferenceservice nvidia-nemotron-nano-9b-v2 -n my-namespace -w

# Get detailed status
oc describe inferenceservice nvidia-nemotron-nano-9b-v2 -n my-namespace
```

### Check Pod Status

```bash
# Get predictor pod
oc get pods -l serving.kserve.io/inferenceservice=nvidia-nemotron-nano-9b-v2 -n my-namespace

# View pod logs
oc logs -f deployment/nvidia-nemotron-nano-9b-v2-predictor -c kserve-container -n my-namespace
```

### Check Storage Initializer Logs

During the initial deployment, the model files are downloaded by the storage-initializer:

```bash
# View download progress
POD=$(oc get pods -l serving.kserve.io/inferenceservice=nvidia-nemotron-nano-9b-v2 -n my-namespace -o jsonpath='{.items[0].metadata.name}')
oc logs $POD -c storage-initializer -n my-namespace
```

## Troubleshooting

### Model Download Taking Too Long

The initial deployment pulls the model from the OCI container registry. The ~18GB model typically loads in 3-5 minutes using the default OCI image. If using S3 storage, downloads may take 5-10 minutes depending on network speed. Monitor progress:

```bash
POD=$(oc get pods -l serving.kserve.io/inferenceservice=nvidia-nemotron-nano-9b-v2 -n my-namespace -o jsonpath='{.items[0].metadata.name}')
oc logs $POD -c storage-initializer -n my-namespace -f
```

### Inference Requests Timing Out

If you see 502 errors or timeouts during long-running inference:

1. Check the route timeout is set correctly (default: 600s)
2. Verify oauth-proxy upstream timeout is configured (default: 10m)
3. Check the pod logs for errors:
   ```bash
   oc logs deployment/nvidia-nemotron-nano-9b-v2-predictor -c kserve-container -n my-namespace
   oc logs deployment/nvidia-nemotron-nano-9b-v2-predictor -c oauth-proxy -n my-namespace
   ```

### GPU Not Available

Ensure your OpenShift cluster has GPU nodes and the NVIDIA GPU operator is installed:

```bash
# Check for GPU nodes
oc get nodes -l nvidia.com/gpu.present=true

# Check GPU operator
oc get pods -n nvidia-gpu-operator
```

## Uninstallation

```bash
# Using Makefile
make nemotron-model-uninstall NAMESPACE=my-namespace

# Or using Helm directly
helm uninstall nemotron-model -n my-namespace
```

## Integration with Copilot Backend

This chart is designed to integrate seamlessly with the copilot-backend service:

```bash
# Deploy model and configure backend automatically (uses OCI image by default)
make copilot-backend-install \
  NAMESPACE=my-namespace \
  DEPLOY_MODEL=true
```

The Makefile will:
1. Deploy the model using this chart with the default OCI container image
2. Wait for the model to be ready
3. Extract the model name from the deployed InferenceService
4. Extract the model endpoint URL from the OpenShift route
5. Extract the API key from the namespace's default service account token
6. Configure copilot-backend with all extracted values automatically

**Note**:
- When `DEPLOY_MODEL=true`, you don't need to specify `copilot.llmBaseUrl`, `copilot.llmModel`, or `copilot.llmApiKey` - they are all automatically extracted
- No S3 configuration required - the deployment uses a pre-built OCI container image by default

## Architecture

```
┌─────────────────┐
│  OpenShift      │
│  Route          │  (HTTPS, 600s timeout)
└────────┬────────┘
         │
┌────────▼────────┐
│  oauth-proxy    │  (Authentication, 10m upstream timeout)
│  (sidecar)      │
└────────┬────────┘
         │
┌────────▼────────┐
│  vLLM Server    │  (Port 8080, PyTorch model)
│  (kserve-       │
│   container)    │
└─────────────────┘
```

## References

- [KServe Documentation](https://kserve.github.io/website/)
- [vLLM Documentation](https://docs.vllm.ai/)
- [NVIDIA Nemotron Model](https://huggingface.co/nvidia/Nemotron-Nano-9B-v2)
- [Red Hat OpenShift AI](https://www.redhat.com/en/technologies/cloud-computing/openshift/openshift-ai)
