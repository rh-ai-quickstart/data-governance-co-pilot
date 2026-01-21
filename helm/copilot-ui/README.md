# Copilot UI Helm Chart

Svelte-based frontend for the Data Governance Copilot.

## Overview

This Helm chart deploys the Svelte UI as a static website served by nginx. The UI connects to the copilot-backend service to provide a chat interface for data governance queries.

## Architecture

```
User Browser
  ↓ HTTPS (OpenShift Route)
nginx (serving static Svelte app)
  ↓ POST /query (configured at build time)
copilot-backend service
```

## Prerequisites

- **copilot-backend** must be deployed first (the UI needs the backend URL at build time)
- OpenShift cluster with sufficient resources

## Installation

### Via Makefile (Recommended)

The Makefile automatically:
1. Gets the copilot-backend route URL
2. Builds the UI with the correct backend URL baked in
3. Deploys the Helm chart

```bash
# From the helm/ directory
make copilot-ui-install NAMESPACE=your-namespace
```

### Manual Installation

1. **Get the backend URL**:
   ```bash
   BACKEND_URL=$(oc get route copilot-backend -o jsonpath='https://{.spec.host}' -n your-namespace)
   echo "Backend URL: $BACKEND_URL"
   ```

2. **Build the image**:
   ```bash
   # Create ImageStream
   oc apply -f imagestream.yaml -n your-namespace

   # Update BuildConfig with backend URL
   cat buildconfig.yaml | sed "s|\${BACKEND_URL}|$BACKEND_URL|g" | oc apply -f - -n your-namespace

   # Start the build (uploads UI source files)
   cd ../..  # Go to project root
   oc start-build copilot-ui --from-dir=. --follow -n your-namespace
   ```

3. **Deploy the chart**:
   ```bash
   helm upgrade --install copilot-ui . \
     --namespace your-namespace \
     --set image.repository=image-registry.openshift-image-registry.svc:5000/your-namespace/copilot-ui \
     --set image.tag=latest \
     --set backend.url=$BACKEND_URL
   ```

4. **Get the UI URL**:
   ```bash
   echo "UI URL: https://$(oc get route copilot-ui -o jsonpath='{.spec.host}' -n your-namespace)"
   ```

## Configuration

### Values

| Parameter | Description | Default |
|-----------|-------------|---------|
| `replicaCount` | Number of replicas | `1` |
| `image.repository` | Image repository | `image-registry.openshift-image-registry.svc:5000/NAMESPACE/copilot-ui` |
| `image.tag` | Image tag | `latest` |
| `service.port` | Service port | `8080` |
| `route.enabled` | Enable OpenShift Route | `true` |
| `route.host` | Custom hostname (optional) | `""` (auto-generated) |
| `backend.url` | Backend URL (set at build time) | `""` |
| `resources.requests.cpu` | CPU request | `100m` |
| `resources.requests.memory` | Memory request | `128Mi` |
| `resources.limits.cpu` | CPU limit | `500m` |
| `resources.limits.memory` | Memory limit | `256Mi` |

## Build Process

The build happens in two stages:

### Stage 1: Node.js Builder
- Installs dependencies (pnpm or npm)
- Sets `VITE_COPILOT_BACKEND_URL` environment variable
- Builds the Svelte app (`npm run build`)
- Output: Static files in `build/` directory

### Stage 2: nginx Runtime
- Uses `nginxinc/nginx-unprivileged:alpine` for OpenShift compatibility
- Copies built files to `/usr/share/nginx/html`
- Configures nginx for SPA routing (all routes → index.html)
- Disables caching for index.html
- Runs as non-root user (UID 1001)

## Backend URL Configuration

**Important**: The backend URL is baked into the UI at **build time**, not runtime. This means:

✅ **Advantages**:
- No runtime configuration needed
- Better security (no env vars exposed in browser)
- Faster initial load (no config fetch)

❌ **Limitation**:
- Changing the backend URL requires rebuilding the image

If the backend route changes, you must rebuild:
```bash
make copilot-ui-install NAMESPACE=your-namespace
```

## Deployment Details

### nginx Configuration

The UI is served by nginx with this configuration:
- Listen on port 8080 (non-privileged)
- Root directory: `/usr/share/nginx/html`
- SPA routing: All requests fallback to `index.html`
- Cache control: index.html is never cached (ensures latest version)

### OpenShift Route

The chart creates an OpenShift Route with:
- TLS termination: edge
- Insecure traffic: redirected to HTTPS
- Auto-generated hostname (or custom if `route.host` is set)

## Usage

Once deployed, users can:

1. **Access the UI** at the route URL
2. **Ask questions** in the chat interface
3. **View tool executions** - see which database analysis tools were used
4. **Manage conversations** - save and restore chat history

Example questions:
- "Show me the database schemas"
- "What are the most expensive queries?"
- "Analyze missing indexes in the users table"
- "Check database health"

## Scaling

The UI can be scaled horizontally for high availability:

```bash
# Manual scaling
oc scale deployment/copilot-ui --replicas=3 -n your-namespace

# Via Helm
helm upgrade copilot-ui . \
  --namespace your-namespace \
  --set replicaCount=3
```

Since the UI is stateless (static files served by nginx), any number of replicas can be run.

## Troubleshooting

### UI shows "Failed to fetch" errors

**Cause**: Backend URL is incorrect or backend is not reachable.

**Fix**:
1. Check what backend URL was baked in:
   ```bash
   oc logs deployment/copilot-ui -n your-namespace | grep VITE_COPILOT_BACKEND_URL
   ```

2. Verify backend route exists:
   ```bash
   oc get route copilot-backend -n your-namespace
   ```

3. Rebuild with correct URL if needed:
   ```bash
   make copilot-ui-install NAMESPACE=your-namespace
   ```

### UI shows blank page

**Cause**: Build failed or nginx misconfigured.

**Fix**:
1. Check build logs:
   ```bash
   oc logs bc/copilot-ui -n your-namespace
   ```

2. Check nginx logs:
   ```bash
   oc logs deployment/copilot-ui -n your-namespace
   ```

3. Verify static files exist:
   ```bash
   oc exec deployment/copilot-ui -n your-namespace -- ls -la /usr/share/nginx/html
   ```

### Build fails with "pnpm not found"

**Cause**: UI source files not uploaded correctly.

**Fix**:
```bash
# Rebuild from project root
cd /path/to/data-governance-co-pilot
oc start-build copilot-ui --from-dir=. --follow -n your-namespace
```

### CORS errors in browser console

**Cause**: Backend is blocking requests from UI domain.

**Fix**: The copilot-backend has CORS enabled for all origins. If you changed this, update the backend's `CORSMiddleware` in [service.py](../../packages/copilot/src/copilot/service.py).

## Updating the UI

To deploy UI changes:

```bash
# Option 1: Via Makefile
make copilot-ui-install NAMESPACE=your-namespace

# Option 2: Manual rebuild
oc start-build copilot-ui --from-dir=. --follow -n your-namespace
```

The deployment will automatically roll out the new image.

## Uninstallation

```bash
# Via Makefile
make copilot-ui-uninstall NAMESPACE=your-namespace

# Or manually
helm uninstall copilot-ui -n your-namespace
```

This removes:
- Deployment
- Service
- Route
- (Image and BuildConfig remain for faster rebuilds)

## Resources

- UI Source Code: [apps/ui/](../../apps/ui/)
- Backend Chart: [../copilot-backend/](../copilot-backend/)
- Architecture Docs: [../../ARCHITECTURE.md](../../ARCHITECTURE.md)

## License

MIT
