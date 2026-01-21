# pg-airman-mcp Patches

This directory contains patches applied to the upstream pg-airman-mcp source during the Docker build process.

## disable-dns-rebinding-protection.patch

**Purpose**: Disables DNS rebinding protection in the MCP Python SDK to allow requests from Kubernetes service mesh.

**Issue**: The MCP Python SDK (version >= 1.8.0) introduced DNS rebinding protection that validates incoming Host headers. When pg-airman-mcp runs in Kubernetes and receives requests from other pods using the service DNS name (e.g., `pg-airman-mcp-service:8000`), the server rejects them with:
```
WARNING  Invalid Host header: pg-airman-mcp-service:8000
INFO:     10.129.2.62:37584 - "POST /mcp HTTP/1.1" 421 Misdirected Request
```

**Solution**: This patch modifies `server.py` to instantiate FastMCP with `TransportSecuritySettings(enable_dns_rebinding_protection=False)`.

**Security Considerations**:
- DNS rebinding protection is disabled because Kubernetes provides its own network security boundaries
- All traffic is within the cluster's internal service mesh
- External access is controlled via Routes/Ingress with proper security configurations

**References**:
- [MCP Python SDK Issue #1798](https://github.com/modelcontextprotocol/python-sdk/issues/1798)
- [MCP Transports Documentation](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports)

**Applied during build**: The patch is applied in `buildconfig.yaml` after cloning the upstream repository and before installing dependencies.
