# pg-airman-mcp libpq5 Fix

## The Problem

The official `enterprisedb/pg-airman-mcp:latest` Docker image fails to start with this error:

```
ImportError: no pq wrapper available.
Attempts made:
- couldn't import psycopg 'c' implementation: libpq.so.5: cannot open shared object file: No such file or directory
- couldn't import psycopg 'binary' implementation: No module named 'psycopg_binary'
- couldn't import psycopg 'python' implementation: libpq library not found
```

## Root Cause

The [official Dockerfile](https://github.com/EnterpriseDB/pg-airman-mcp/blob/main/Dockerfile) installs `libpq-dev` (development headers) but **not `libpq5`** (the actual runtime library) in the final runtime stage.

**What's in the image:**
- `libpq-dev` - Development headers and `pg_config` utility
- ❌ Missing: `libpq5` - The actual PostgreSQL client library

**What psycopg needs:**
- `libpq.so.5` - The shared library file (provided by `libpq5` package)

## Why We Can't Fix It at Runtime

On OpenShift, containers run as non-root with random UIDs by design. We cannot:
- ❌ Install packages at runtime (requires root)
- ❌ Use init containers to install dependencies (still requires root)
- ❌ Override the entrypoint to run `apt-get install`

## The Solution: Custom Image Build

We build a **fixed custom image** using OpenShift BuildConfig that includes `libpq5`.

### Files Created

1. **buildconfig.yaml** - OpenShift BuildConfig with inline Dockerfile
   - Clones the official pg-airman-mcp repo
   - Installs `libpq5` in the runtime stage
   - Makes the image OpenShift-compatible (arbitrary UIDs)

2. **imagestream.yaml** - ImageStream to store the built image

3. **Makefile target** - `build-pg-airman-mcp-image`
   - Creates ImageStream
   - Creates BuildConfig
   - Triggers the build
   - Waits for completion

### The Fix in Detail

**Original Dockerfile (broken):**
```dockerfile
FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y \
    dnsutils \
    iputils-ping \
    libpq-dev \    # <-- Only dev headers, not the runtime library!
    net-tools
```

**Our Fixed Dockerfile:**
```dockerfile
FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \        # <-- THE FIX: Runtime library
    dnsutils \
    iputils-ping \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

# OpenShift compatibility
RUN chmod -R g=u /app && \
    chgrp -R 0 /app
USER 1000
```

## How It Works

### Build Process

1. **Makefile calls build-pg-airman-mcp-image**:
   ```bash
   make pg-airman-mcp-install NAMESPACE=myns ...
   ```

2. **BuildConfig inline Dockerfile**:
   - Uses multi-stage build (builder + runtime)
   - Builder stage: Clones repo, installs with `uv`
   - Runtime stage: Installs `libpq5` + copies app
   - Makes directories group-writable for OpenShift

3. **OpenShift builds the image**:
   - Stores in internal registry: `image-registry.openshift-image-registry.svc:5000/NAMESPACE/pg-airman-mcp:latest`

4. **Helm chart deploys with custom image**:
   ```yaml
   image:
     repository: image-registry.openshift-image-registry.svc:5000/NAMESPACE/pg-airman-mcp
     tag: latest
   ```

### Deployment Flow

```
make pg-airman-mcp-install
  │
  ├─► build-pg-airman-mcp-image
  │     ├─► Create ImageStream
  │     ├─► Create BuildConfig (inline Dockerfile with libpq5)
  │     ├─► oc start-build (5-10 minutes)
  │     └─► Image: NAMESPACE/pg-airman-mcp:latest
  │
  └─► helm install pg-airman-mcp
        ├─► Use custom image from internal registry
        ├─► Deploy pod with fixed image
        └─► ✅ Starts successfully with libpq5
```

## Testing the Fix

### Verify Build

```bash
# Check ImageStream
oc get imagestream pg-airman-mcp -n NAMESPACE

# Check BuildConfig
oc get buildconfig pg-airman-mcp -n NAMESPACE

# View build logs
oc logs -f build/pg-airman-mcp-1 -n NAMESPACE
```

### Verify Deployment

```bash
# Check pod status
oc get pods -l app.kubernetes.io/name=pg-airman-mcp -n NAMESPACE

# View logs (should show successful startup)
oc logs -l app.kubernetes.io/name=pg-airman-mcp -n NAMESPACE

# Should see:
# ✅ "SSE transport detected..."
# ✅ No ImportError about libpq.so.5
```

### Test libpq5 Installation

```bash
# Exec into the pod
oc exec -it deployment/pg-airman-mcp -n NAMESPACE -- /bin/bash

# Check if libpq5 is installed
dpkg -l | grep libpq
# Should show: libpq5

# Check if the library file exists
ls -la /usr/lib/*/libpq.so.5
# Should exist

# Test Python import
python3 -c "from psycopg import sql; print('Success!')"
# Should print: Success!
```

## Alternative Solutions (Not Used)

### Option 1: Wait for Official Fix
- ❌ Blocked on upstream maintainers
- ❌ Unknown timeline
- ❌ Not acceptable for production

### Option 2: Use Different Base Image
- ❌ Requires forking the entire project
- ❌ Maintenance burden

### Option 3: Build Locally, Push to Registry
- ❌ Requires external image registry
- ❌ More complex CI/CD
- ✅ Works, but OpenShift BuildConfig is simpler

## Why Our Solution is Best

1. ✅ **Automatic**: Build happens during `make install`
2. ✅ **Self-contained**: Uses OpenShift internal registry
3. ✅ **Repeatable**: BuildConfig stays in cluster
4. ✅ **OpenShift-native**: Uses standard BuildConfig pattern
5. ✅ **No external dependencies**: No Docker Hub, no external registry
6. ✅ **Maintainable**: Inline Dockerfile in BuildConfig
7. ✅ **Minimal changes**: Only adds `libpq5`, rest is identical

## Reporting Upstream

This issue should be reported to the pg-airman-mcp project:
- GitHub: https://github.com/EnterpriseDB/pg-airman-mcp/issues
- Issue title: "Docker image missing libpq5 runtime library"
- Fix: Add `libpq5` to Dockerfile runtime stage

Example PR:
```dockerfile
# In Dockerfile, runtime stage
RUN apt-get update && apt-get install -y --no-install-recommends \
+   libpq5 \
    dnsutils \
    iputils-ping \
    libpq-dev \
    net-tools
```

## Cleanup

To rebuild the image after upstream fixes:

```bash
# Delete the build
oc delete build pg-airman-mcp-1 -n NAMESPACE

# Delete BuildConfig and ImageStream
oc delete buildconfig pg-airman-mcp -n NAMESPACE
oc delete imagestream pg-airman-mcp -n NAMESPACE

# Update values.yaml to use official image
# helm upgrade pg-airman-mcp ... --set image.repository=enterprisedb/pg-airman-mcp
```
