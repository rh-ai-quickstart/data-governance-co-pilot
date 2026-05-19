# Session Affinity and CORS Security

## Overview

This document explains the session affinity configuration and CORS security measures for the Data Governance Copilot.

## What Are Cookies Used For?

The application uses cookies **solely for session affinity** (sticky sessions) to route requests to the same backend pod.

### Cookie Contents

**HAProxy Session Cookie:**
```
98586ee2a2931b8d619f1a2f3cc259f8=ff39a6b9507e8afc02cd536de3ec4f0f
```

- **What it contains**: A routing token (hash) that identifies a backend pod
- **What it does NOT contain**: User credentials, session data, authentication tokens, or any sensitive information
- **Purpose**: Load balancer routing only

**Cookie Security Attributes:**
- ✅ `HttpOnly` - Prevents JavaScript access (XSS mitigation)
- ✅ `Secure` - Only transmitted over HTTPS
- ✅ `SameSite=None` - Required for cross-origin requests (UI and backend on different subdomains)

## Why Session Affinity is Needed

### Problem Without Session Affinity

The application stores conversation state in memory:
- Each copilot-backend pod has its own `conversation_store` dictionary
- Each pg-airman-mcp pod maintains database connection state
- Without affinity, requests round-robin between pods → lose conversation context

### Solution: Two-Layer Session Affinity

**Layer 1: Browser → Backend (HAProxy Cookie)**
```
User Browser → OpenShift Router (HAProxy) → copilot-backend pod A
                     ↓ (sets cookie: copilot-backend-route)
User Browser ← OpenShift Router ← copilot-backend pod A

Next Request:
User Browser → OpenShift Router → copilot-backend pod A (same!)
    (sends cookie)     ↓ (reads cookie)
```

**Configuration:**
- OpenShift Route annotations (automatic via HAProxy)
- UI sends `credentials: 'include'` in fetch requests
- Cookie-based routing for 3 hours (`timeoutSeconds: 10800`)

**Layer 2: Backend → MCP (ClientIP Affinity)**
```
copilot-backend pod A → pg-airman-mcp service → MCP pod X
       (IP: 10.x.x.1)         ↓ (sessionAffinity: ClientIP)
                          (routes based on source IP)
```

**Configuration:**
- `sessionAffinity: ClientIP` in [pg-airman-mcp service](helm/pg-airman-mcp/templates/service.yaml#L15)
- Each backend pod has unique cluster IP → routes to same MCP pod

## CORS Security Configuration

### The Problem

**Previous Configuration (Insecure):**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # ⚠️ DANGEROUS!
    allow_credentials=True,     # ⚠️ Combined with wildcard = CSRF vulnerability
)
```

**Attack Scenario:**
1. User visits legitimate app and gets session cookie
2. User visits malicious site `evil.com`
3. `evil.com` makes requests to copilot-backend with user's cookie
4. Backend accepts because `allow_origins=["*"]`
5. Attacker can make authenticated requests on behalf of the user

### Fixed Configuration

**[service.py](packages/copilot/src/copilot/service.py):**
```python
# SECURITY: Restrict origins when using credentials
allowed_origins = os.getenv("COPILOT_UI_ORIGIN", "").split(",") 
if allowed_origins == ["*"] and os.getenv("COPILOT_ALLOW_ALL_ORIGINS") != "true":
    logger.warning("SECURITY WARNING: CORS configured with wildcard origins...")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,                    # Restrict to specific origins
    allow_credentials=True,
    allow_methods=["POST", "GET", "DELETE", "OPTIONS"],  # Only needed methods
    allow_headers=["Content-Type", "Accept"],         # Only needed headers
)
```

**Environment Variable:**
- `COPILOT_UI_ORIGIN` - Comma-separated list of allowed origins
- Example: `https://copilot-ui-namespace.apps.cluster.com`

### Security Levels

| Configuration | Security | Use Case |
|--------------|----------|----------|
| `COPILOT_UI_ORIGIN` set to specific origins | ✅ Secure | **Production** |
| `COPILOT_UI_ORIGIN` empty (wildcard) | ⚠️ Warning logged | Development only |
| `COPILOT_ALLOW_ALL_ORIGINS=true` | ❌ No warning | Testing only (NOT production) |

## Deployment Configuration

### Automatic Configuration (Recommended)

**When using `make install`:**

The Makefile **automatically** configures CORS security:

1. Deploys copilot-backend (initially with empty CORS config, logs warning)
2. Deploys copilot-ui (creates OpenShift Route)
3. Extracts UI route URL: `https://copilot-ui-namespace.apps.cluster.com`
4. Updates copilot-backend with `COPILOT_UI_ORIGIN` environment variable
5. Backend restarts with secure CORS configuration

**No manual configuration needed!**

```bash
make install NAMESPACE=myns postgres.userId=postgres \
  postgres.password=pass123 \
  postgres.databaseName=postgres \
  postgres.readonlyPassword=readonly123
```

**Makefile Implementation:**
```bash
# After copilot-ui deployment (helm/Makefile):
UI_ORIGIN="https://$(oc get route copilot-ui -o jsonpath='{.spec.host}' -n $(NAMESPACE))"
oc set env deployment/copilot-backend COPILOT_UI_ORIGIN="$UI_ORIGIN" -n $(NAMESPACE)
```

### Manual Configuration (If not using Makefile)

**Option 1: Set in values.yaml**
```yaml
cors:
  allowedOrigins: "https://copilot-ui-myns.apps.cluster.com"
```

**Option 2: Update after deployment**
```bash
# Get UI route
UI_ORIGIN=$(oc get route copilot-ui -n myns -o jsonpath='https://{.spec.host}')

# Update backend deployment
oc set env deployment/copilot-backend \
  COPILOT_UI_ORIGIN="$UI_ORIGIN" \
  -n myns
```

### Development (Temporary Wildcard)

If deploying manually during development and you want to skip CORS restrictions temporarily:

**Helm values.yaml:**
```yaml
cors:
  allowedOrigins: ""  # Empty = wildcard with warning
```

**Behavior:**
- Logs warning on startup
- Accepts requests from any origin
- Suitable for development/testing only
- **NOT recommended for production**

## Files Modified

### Frontend (UI)
1. **[ChatInterface.svelte](apps/ui/src/lib/components/ChatInterface.svelte)**
   - Added `credentials: 'include'` to `/query/stream` requests
   - Added `credentials: 'include'` to `/provider/info` requests

2. **[PolicyUpload.svelte](apps/ui/src/lib/components/PolicyUpload.svelte)**
   - Added `credentials: 'include'` to `/policy/status` requests
   - Added `credentials: 'include'` to `/policy/upload` requests
   - Added `credentials: 'include'` to `/policy` DELETE requests

### Backend
3. **[service.py](packages/copilot/src/copilot/service.py)**
   - Added CORS origin validation
   - Added security warning for wildcard origins
   - Restricted allowed methods and headers

4. **[deployment.yaml](helm/copilot-backend/templates/deployment.yaml)**
   - Added `COPILOT_UI_ORIGIN` environment variable

5. **[values.yaml](helm/copilot-backend/values.yaml)**
   - Added `cors.allowedOrigins` configuration

## Verification

### Check Session Affinity

**Browser DevTools:**
1. Open DevTools → Network tab
2. Make a query in the UI
3. Check Response Headers for `Set-Cookie: <hash>=<pod-id>; ...`
4. Subsequent requests should send this cookie in Request Headers

**Backend Logs:**
```bash
# Get backend pods
oc get pods -n myns | grep copilot-backend

# Make a query, then check which pod handled it
oc logs -f copilot-backend-<pod-id> -n myns
```

**Expected:** All requests from same browser session go to same pod

### Check CORS Configuration

**Startup Logs:**
```bash
oc logs deployment/copilot-backend -n myns | grep -i "cors\|security"
```

**Expected Output (Production):**
- No warnings if `COPILOT_UI_ORIGIN` is set

**Expected Output (Development):**
```
SECURITY WARNING: CORS configured with wildcard origins and credentials enabled.
Set COPILOT_UI_ORIGIN environment variable to restrict access.
```

## Security Recommendations

### For Production Deployments

1. ✅ **Always set `COPILOT_UI_ORIGIN`** to specific origins
2. ✅ **Use HTTPS** for all routes (already configured)
3. ✅ **Monitor backend logs** for security warnings
4. ✅ **Review CORS configuration** if changing deployment architecture
5. ❌ **Never use wildcard origins** with `allow_credentials=True` in production

### Additional Hardening (Future Enhancements)

1. **CSRF Tokens**: Add explicit CSRF token validation
2. **Redis Session Store**: Replace in-memory conversation store with Redis for true multi-pod scalability
3. **Content Security Policy**: Add CSP headers to prevent XSS
4. **Rate Limiting**: Add per-IP rate limiting to prevent abuse
5. **Audit Logging**: Log all API requests with user context

## References

- [CORS MDN Documentation](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS)
- [OWASP CSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)
- [OpenShift Route Configuration](https://docs.openshift.com/container-platform/latest/networking/routes/route-configuration.html)
