# Network Policy Configuration

## Status: DISABLED

**NetworkPolicies are currently disabled** and moved to `helm/*/disabled/` folders due to ongoing DNS resolution issues.

Even with completely permissive NetworkPolicy rules (allow all ingress, allow port 53 egress to any destination), DNS queries were failing. This suggests a deeper issue with NetworkPolicy implementation in this specific OpenShift environment.

NetworkPolicy files have been preserved in disabled/ folders for future re-enablement once the root cause is identified.

## Overview

NetworkPolicies implement zero-trust network segmentation for the Data Governance Copilot. Each component has explicit allow rules - all other traffic is denied by default.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ Internet / User Browser                                         │
└────────────────────────────┬────────────────────────────────────┘
                             │
                ┌────────────▼────────────┐
                │ OpenShift Router        │
                │ (Ingress Controller)    │
                └────────────┬────────────┘
                             │
           ┌─────────────────┼─────────────────┐
           │                 │                 │
    ┌──────▼──────┐   ┌──────▼──────┐         │
    │ copilot-ui  │   │ copilot-    │         │
    │             ├──►│ backend     │◄────────┘
    └─────────────┘   └──────┬──────┘
                             │
                    ┌────────┼────────┐
                    │        │        │
             ┌──────▼──────┐ │ ┌─────▼──────────┐
             │ pg-airman-  │ │ │ External LLM   │
             │ mcp         │ │ │ (HTTPS)        │
             └──────┬──────┘ │ └────────────────┘
                    │        │
             ┌──────▼──────┐ │
             │ PostgreSQL  │ │
             │ (pgvector)  │ │
             └─────────────┘ │
                             │
                    ┌────────▼────────┐
                    │ DNS (OpenShift) │
                    └─────────────────┘
```

## NetworkPolicy Details

### 1. copilot-ui ([networkpolicy.yaml](../helm/copilot-ui/templates/networkpolicy.yaml))

**Ingress:**
- ✅ From openshift-dns namespace (any port, UDP/TCP) - DNS responses
- ✅ From OpenShift Router (port 8080) - uses label `policy-group.network.openshift.io/ingress: ""`
- ✅ From OpenShift Monitoring (port 8080) - for metrics collection
- ❌ All other ingress DENIED

**Egress:**
- ✅ To any destination on port 53 (UDP/TCP) - permissive DNS for troubleshooting
- ✅ To copilot-backend service (port 8080) - uses service CIDR ipBlock
- ❌ All other egress DENIED

### 2. copilot-backend ([networkpolicy.yaml](../helm/copilot-backend/templates/networkpolicy.yaml))

**Ingress:**
- ✅ From openshift-dns namespace (any port, UDP/TCP) - DNS responses
- ✅ From copilot-ui pods (port 8080)
- ✅ From OpenShift Router (port 8080) - for direct API access, uses label `policy-group.network.openshift.io/ingress: ""`
- ✅ From OpenShift Monitoring (port 8080) - for metrics collection
- ❌ All other ingress DENIED

**Egress:**
- ✅ To any destination on port 53 (UDP/TCP) - permissive DNS for troubleshooting
- ✅ To pg-airman-mcp service (port 8000) - uses service CIDR ipBlock
- ✅ To external LLM endpoints (ports 80, 443) via internet (0.0.0.0/0)
  - Only excludes 192.168.0.0/16 (common home networks)
  - Does NOT exclude 10.0.0.0/8 or 169.254.169.0/24 - OpenShift Routes/DNS may use these ranges
- ❌ All other egress DENIED

**Note:** External LLM access is intentionally permissive to avoid blocking OpenShift internal routes. For production, consider restricting to specific LLM provider IP ranges if using external endpoints.

### 3. pg-airman-mcp ([networkpolicy.yaml](../helm/pg-airman-mcp/templates/networkpolicy.yaml))

**Ingress:**
- ✅ From openshift-dns namespace (any port, UDP/TCP) - DNS responses
- ✅ From copilot-backend pods (port 8000)
- ✅ From OpenShift Monitoring (port 8000) - for metrics collection
- ❌ All other ingress DENIED

**Egress:**
- ✅ To any destination on port 53 (UDP/TCP) - permissive DNS for troubleshooting
- ✅ To PostgreSQL service (port 5432) - uses podSelector for direct pod-to-pod
- ❌ All other egress DENIED

## Security Benefits

1. **Lateral Movement Prevention**: Even if one component is compromised, attackers cannot freely access other services
2. **Blast Radius Containment**: Network isolation limits the impact of security incidents
3. **Compliance**: Demonstrates network segmentation for SOC2, PCI-DSS, and similar frameworks
4. **Zero-Trust Architecture**: Explicit allow-list approach - nothing is trusted by default
5. **Defense in Depth**: Network policies complement other security controls (RBAC, SecurityContext, etc.)

## OpenShift OVN-Kubernetes Behavior

**Critical**: NetworkPolicy evaluation happens **BEFORE** OVN-Kubernetes performs DNAT:

1. Application sends request to service ClusterIP (e.g., DNS at 172.30.0.10 or `pg-airman-mcp-service` at 172.30.107.144)
2. **Egress NetworkPolicy evaluates first** - it sees the original service ClusterIP destination
3. If allowed, OVN-Kubernetes then DNATs the destination to a backend pod IP
4. Therefore, egress rules must allow traffic to the **service network CIDR** (172.30.0.0/16)

### DNS Configuration

**Critical**: DNS requires **both** egress and ingress rules:

**Egress** (DNS queries):
```yaml
- ports:
  - protocol: UDP
    port: 53
  - protocol: TCP
    port: 53
```

**Ingress** (DNS responses):
```yaml
- from:
  - namespaceSelector:
      matchLabels:
        kubernetes.io/metadata.name: openshift-dns
  ports:
  - protocol: UDP
  - protocol: TCP
```

DNS responses arrive from the openshift-dns namespace on ephemeral ports (random high ports). Without ingress rules allowing responses from the DNS namespace, DNS queries will time out even though egress is allowed.

### Service-to-Service Communication

For service-to-service communication within the namespace:
- Use `ipBlock` with service CIDR for predictable behavior through the service layer
- Alternatively, use `podSelector` which allows direct pod-to-pod traffic (bypasses service layer)

## OpenShift Compatibility

These NetworkPolicies use OpenShift-specific labels and dynamic CIDR detection:
- **Router/Ingress**: `policy-group.network.openshift.io/ingress: ""` (preferred label for OpenShift 4.x)
  - Legacy label `network.openshift.io/policy-group: ingress` also works but is not recommended
- **Monitoring**: `network.openshift.io/policy-group: monitoring`
- **Pod Network CIDR**: Dynamically detected via Helm lookup of `networks.config.openshift.io/v1/cluster` → `status.clusterNetwork[0].cidr`
- **Service Network CIDR**: Dynamically detected via Helm lookup of `networks.config.openshift.io/v1/cluster` → `status.serviceNetwork[0]`

If deploying to vanilla Kubernetes:
- Replace OpenShift-specific namespace selectors with your cluster's ingress controller and monitoring namespaces
- Set pod and service CIDR manually in values.yaml (cannot use Helm lookup without OpenShift API)
- Check your CNI plugin's DNAT behavior - some CNIs evaluate NetworkPolicy before DNAT

## Deployment

**Current Status**: NetworkPolicies are DISABLED.

To re-enable, move files from `disabled/` back to `templates/`:
```bash
mv helm/copilot-backend/disabled/networkpolicy.yaml helm/copilot-backend/templates/
mv helm/copilot-ui/disabled/networkpolicy.yaml helm/copilot-ui/templates/
mv helm/pg-airman-mcp/disabled/networkpolicy.yaml helm/pg-airman-mcp/templates/
make install
```

## Verification

Check that NetworkPolicies are applied:

```bash
kubectl get networkpolicy -n <namespace>
```

Test connectivity:

```bash
# From copilot-backend to pg-airman-mcp (should succeed)
kubectl exec -n <namespace> deployment/copilot-backend -- curl -v http://pg-airman-mcp-service:8000/health

# From copilot-ui to pg-airman-mcp (should fail - blocked by NetworkPolicy)
kubectl exec -n <namespace> deployment/copilot-ui -- curl -v http://pg-airman-mcp-service:8000/health
```

## Future Enhancements

1. **Egress IP Restrictions**: Replace broad internet egress (0.0.0.0/0) with specific CIDR blocks for known LLM endpoints (e.g., OpenAI, Azure OpenAI, AWS Bedrock)
2. **PostgreSQL NetworkPolicy**: Add NetworkPolicy for pgvector database (currently unprotected)
3. **NetworkPolicy Violation Alerts**: Configure alerts on NetworkPolicy drops using OpenShift monitoring
4. **Calico/Cilium**: For advanced features (DNS-based egress rules, L7 policies, encryption), consider Calico or Cilium CNI plugins
5. **Namespace-level Default Policy**: Add deny-all default NetworkPolicy to project template for automatic deployment
