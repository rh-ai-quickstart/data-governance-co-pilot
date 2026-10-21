# Helm Charts - Data Governance Copilot

This directory contains Helm charts for deploying the data governance solution components.

## Available Charts

- **pgvector** - PostgreSQL database with pgvector extension
- **pgadmin** - Database administration UI
- **pg-airman-mcp** - EnterpriseDB's MCP server for enabling agentic applications that connect to PostgreSQL databases
- **copilot-backend** - Microservice to support the user interface (contains MCP client)
- **copilot-ui** - Sveltekit based user interface
- **nemotron-model** - Deployment artifacts for Nvidia's Nemotron Nano v2 model

## Quick Start

### Full Installation

Install all components (pgvector, pgadmin, etc.). The namespace you provide below will be created automatically the installation. Do not install 
into an existing namespace! Keep in mind that uninstallation (shown below) removes every object in the namespace and deletes the namespace.

**Step 1:** Login to your OpenShift cluster

First, login to your OpenShift console. After logging in, download the oc terminal command (if you haven't already) by clicking the ? button  in the top
right and selecting Command Line Tools. Download the oc tool for your local platform (e.g.,, your laptop running Mac OS).

To generate the oc login command, click on your user name in the top-right and select 'Copy login command'. Follow the instructions to see your login command in your browser.
Copy the command, paste it into your local terminal and execute it. You are now logged in to your remote cluster and any make, oc or helm commands you execute locally will be directed
to this remote cluster.

**Step 2:** Run the make build command in your local terminal

```bash
make install NAMESPACE=your-namespace MODEL=nemotron DEPLOY_MODEL=true postgres.userId=postgres postgres.password=postgres postgres.readonlyPassword=ReadOnly123 postgres.databaseName=postgres DEPLOY_PGADMIN=true pgadmin.email=yourname@redhat.com pgadmin.password=postgres
```

**Step 3:** Wait for installation to complete and login to the Copilot using your browser. The URL will be printed in your terminal when installation completes.

### Installation without Nemotron

The quickstart can skip installation of the Nemotron LLM if you prefer to use your own LLM. Take the following steps:

**Step 1:** Modify these values in the values.yaml file in the copilot-backend helm chart:

llm.baseUrl: "https://yourmodel-endpoint.domain.com/v1"
llm.model: "your model name"
llm.maxContextLength: an integer that specifies the effective model context length

(#Note: When deploying your own model, you must configure your model with a max length as well. It may equal to or greater than this value.)

**Step 2:** Run the make install command as above, except omit the DEPLOY_MODEL flag and provide a value for llm.apiKey (see example below)

```bash
make install NAMESPACE=yournamespace MODEL=nemotron postgres.userId=postgres postgres.password=postgres postgres.readonlyPassword=ReadOnly123 postgres.databaseName=postgres llm.apiKey=eyJhbGc...iOiJ
```

## Access Modes

**pg-airman-mcp** supports two access modes:

- **`restricted`** (default, recommended for production):
  - Read-only operations
  - Query timeout limits
  - Safe for production environments

- **`unrestricted`** (development only):
  - Full read-write access
  - No query timeouts
  - Use only in development/testing

## Accessing Services

### pgAdmin

pgadmin is deployed with this quickstart to help troubleshooting.

After installation, get the pgAdmin URL:

```bash
oc get route pgadmin -n your-deployed-namespace -o jsonpath='{.spec.host}'
```

### pg-airman-mcp

The MCP server is available internally at:

```
http://pg-airman-mcp-service:8000/mcp
```

This endpoint is (without '/mcp') injected into each pod as the environment variable: PG_AIRMAN_MCP_SERVICE_PORT

To access from outside the cluster (for local development):

```bash
oc port-forward svc/pg-airman-mcp-service 8000:8000 -n your-deployed-namespace
```
Then connect to: `http://localhost:8000/mcp`

## Uninstallation

### Remove All Components and Delete Namespace

**WARNING**: The uninstallation command removes every object in the namespace and deletes the namespace.

```bash
make uninstall NAMESPACE=your-namespace
```

## Configuration Reference

### Required Parameters

The user IDs and passwords you provide below for the postgres database (and pgadmin, if `DEPLOY_PGADMIN=true`) are used to configure the installation with the passwords;
i.e., you are not providing credentials for an existing installation.

| Parameter | Description | Example |
|-----------|-------------|---------|
| `NAMESPACE` | OpenShift/Kubernetes namespace | `your-namespace` |
| `postgres.userId` | PostgreSQL username | `postgres` |
| `postgres.password` | PostgreSQL password | `securepass123` |
| `postgres.databaseName` | Database name | `governance` |
| `postgres.readonlyPassword` | Password for the `mcp_readonly` user used by the MCP server | - |
| `pgadmin.email` | pgAdmin login email (required if `DEPLOY_PGADMIN=true`) | - |
| `pgadmin.password` | pgAdmin password (required if `DEPLOY_PGADMIN=true`) | - |

See the makefile for other optional parameters.

## Chart Details

### pgvector Chart

Deploys PostgreSQL with:
- pgvector extension for vector operations
- StatefulSet for data persistence
- Data loading job for initial dataset
- Data loading uses an ephemeral container whose image is built directly on the cluster using an OpenShift image stream and build config
- Service for internal cluster access

### pg-airman-mcp Chart

Deploys MCP server with:
- Official `enterprisedb/pg-airman-mcp` Docker image
- Streaming HTTP transport for HTTP-based MCP communication
- Configurable access mode (restricted/unrestricted)
- Health checks and readiness probes
- Service for client connections
- To work around limitations in the official image, a custom image is built with this quickstart using an image stream and build config.

**Available MCP Tools**:
- Schema introspection
- SQL execution
- Query analysis and explain plans
- Index recommendations
- Database health checks

See [pg-airman-mcp/README.md](pg-airman-mcp/README.md) for detailed documentation.

## Development Workflow

Import this VSCode workspace into your VS Code application.

Remember to login to your remote OpenShift cluster using the oc login command generated by the OpenShift console (instructions provided earlier).

As you make modifications, run the make install command as shown above to test.

You may also run the build selectively for one component. For example, you can build and deploy just the UI by running the following commands:

**Step 1:** Run make

```bash
make copilot-ui-install NAMESPACE=your-namespace BUILD_COPILOT_UI=true
```

**Step 2:** Update running UI container to pickup the new UI container image the above command builds

```bash
oc rollout restart deployment/copilot-ui -n your-namespace
```

Selective building and deployment is much faster than redeploying the entire application. See the. makefile for other targets you can choose. Remember that the makefile
may apply a common set of validation rules to targets even when they aren't needed, so be sure to use the full make command shown above.

## Troubleshooting

### Check Deployment Status

```bash
# All pods
oc get pods -n your-namespace

# Specific service
oc get pods -l app.kubernetes.io/name=pg-airman-mcp -n your-namespace
```

### View Logs

```bash
# pg-airman-mcp logs
oc logs -l app.kubernetes.io/name=pg-airman-mcp -n your-namespace -f

# Database logs
oc logs pgvector-0 -n your-namespace -f
```