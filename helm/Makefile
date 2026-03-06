# Namespace must be set unless the target is help
ifeq ($(NAMESPACE),)
ifeq (,$(filter help,$(MAKECMDGOALS)))
$(error NAMESPACE is not set)
endif
endif

# Suppress directory change messages
MAKEFLAGS += --no-print-directory

MINIO_CHART := minio
POSTGRES_CHART := pgvector
# pgAdmin chart for database administration UI
PGADMIN_CHART := pgadmin
# pg-airman-mcp chart for PostgreSQL MCP server
PG_AIRMAN_MCP_CHART := pg-airman-mcp
# nemotron-model chart for NVIDIA Nemotron LLM deployment
NEMOTRON_MODEL_CHART := nemotron-model
# qwen3-model chart for Qwen3-14B LLM deployment
QWEN3_MODEL_CHART := qwen3-model
# copilot-backend chart for FastAPI backend service
COPILOT_BACKEND_CHART := copilot-backend
# copilot-ui chart for Svelte frontend
COPILOT_UI_CHART := copilot-ui
# copilot-llama-stack chart for Llama Stack distribution
COPILOT_LLAMA_STACK_CHART := copilot-llama-stack

# Flag to control whether to deploy the LLM model (default: false)
# Set to true to automatically deploy LLM model
DEPLOY_MODEL ?= false

# Flag to control whether to deploy MinIO (default: false)
DEPLOY_MINIO ?= false

# Flag to control whether to deploy pgAdmin (default: false)
DEPLOY_PGADMIN ?= false

# Llama Stack configuration (can be overridden)
LLAMA_STACK_DISTRIBUTION_NAME ?= copilot-llama-stack
LLAMA_STACK_SERVICE_PORT ?= 8321

# Model to deploy (default: qwen3)
# Options: nemotron, qwen3
MODEL ?= qwen3

# Model options:
# - nemotron: NVIDIA Nemotron Nano 9B v2 (MCP-Direct mode only, custom tool calling)
#   * DEPLOY_MODEL=true: Deploy to cluster via KServe
#   * DEPLOY_MODEL=false: Use external endpoint (llm.baseUrl, llm.model, llm.apiKey can be overridden)
# - qwen3: Qwen3-14B (Both modes supported, OpenAI function calling)
#   * DEPLOY_MODEL=true: Deploy to cluster via KServe (pulls from HuggingFace)
#   * DEPLOY_MODEL=false: Use external endpoint (llm.baseUrl can be overridden)

# Provider mode for copilot backend (default: mcp_direct)
# Options: mcp_direct, llama_stack
PROVIDER_MODE ?= mcp_direct

MINIMUM_OC_VERSION = "4.17.0"
MINIMUM_USERID_LENGTH = 3
MINIMUM_PASSWORD_LENGTH = 8

# Default target
.PHONY: help
help:
	@echo "Available targets:"
	@echo "  install       - Installs quickstart and supporting resources"
	@echo "                  Required: NAMESPACE, postgres.userId, postgres.password, postgres.databaseName"
	@echo "                  Optional: DEPLOY_MODEL=true, DEPLOY_MINIO=true, DEPLOY_PGADMIN=true, MODEL=nemotron|qwen3, PROVIDER_MODE=mcp_direct|llama_stack"
	@echo "                  If DEPLOY_MINIO=true: minio.userId, minio.password are required"
	@echo "                  If DEPLOY_PGADMIN=true: pgadmin.email, pgadmin.password are required"
	@echo "                  Example (Nemotron): make install NAMESPACE=myns MODEL=nemotron DEPLOY_MODEL=true PROVIDER_MODE=mcp_direct ..."
	@echo "                  Example (Qwen3): make install NAMESPACE=myns MODEL=qwen3 PROVIDER_MODE=llama_stack llm.apiKey=sk-xxx ..."
	@echo "  pg-airman-mcp-install - Installs pg-airman-mcp MCP server (builds custom image with libpq5 fix)"
	@echo "                  Required: NAMESPACE, postgres.userId, postgres.password, postgres.databaseName"
	@echo "                  Optional: pgairman.accessMode (default: restricted)"
	@echo "                  Note: First run builds custom image (5-10 minutes), subsequent runs are faster"
	@echo "  nemotron-model-install - Deploys NVIDIA Nemotron Nano 9B v2 model using KServe"
	@echo "                  Required: NAMESPACE"
	@echo "                  Optional: model.storage.s3Bucket, model.storage.uri"
	@echo "                  Example: make nemotron-model-install NAMESPACE=myns"
	@echo "                  Note: Uses quay.io/eformat/nvidia-nemotron-nano-9b-v2 OCI image by default"
	@echo "  qwen3-model-install     - Deploys Qwen3-14B model using KServe"
	@echo "                  Required: NAMESPACE"
	@echo "                  Optional: model.storage.s3Bucket, model.storage.uri"
	@echo "                  Example: make qwen3-model-install NAMESPACE=myns"
	@echo "                  Note: Pulls from HuggingFace hf://Qwen/Qwen3-14B by default (public, no token needed)"
	@echo "  copilot-backend-install - Installs copilot backend service (FastAPI orchestration layer)"
	@echo "                  Required: NAMESPACE"
	@echo "                  Optional: DEPLOY_MODEL=true (auto-extracts llmBaseUrl, llmModel, and llmApiKey from deployed model)"
	@echo "                  If DEPLOY_MODEL=false: llm.baseUrl, llm.model, llm.apiKey can be overridden (defaults from values.yaml)"
	@echo "                  Example: make copilot-backend-install NAMESPACE=myns DEPLOY_MODEL=true"
	@echo "                  Note: First run builds custom image (3-5 minutes), subsequent runs are faster"
	@echo "  copilot-ui-install - Installs copilot frontend (Svelte UI)"
	@echo "                  Required: NAMESPACE"
	@echo "                  Note: First run builds custom image (3-5 minutes), subsequent runs are faster"
	@echo "  uninstall     - Uninstalls the quickstart and clean up resources"
	@echo ""
	@echo "Configuration options (set via environment variables or make arguments):"
	@echo "  NAMESPACE                - Target namespace (required)"
	@echo "  DEPLOY_MODEL             - Set to 'true' to auto-deploy and configure LLM model (default: false)"
	@echo "  DEPLOY_MINIO             - Set to 'true' to deploy MinIO object storage (default: false)"
	@echo "  DEPLOY_PGADMIN           - Set to 'true' to deploy pgAdmin web UI (default: false)"
	@echo "  MODEL                    - Model to deploy: nemotron or qwen3 (default: qwen3)"
	@echo "                             nemotron: NVIDIA Nemotron Nano 9B v2 (custom tool calling, MCP-Direct only)"
	@echo "                             qwen3: Qwen3 14B via remote LiteLLM (OpenAI function calling, Llama Stack only)"
	@echo "  PROVIDER_MODE            - LLM provider mode: mcp_direct or llama_stack (default: mcp_direct)"
	@echo "                             mcp_direct: Backend connects directly to vLLM (use with MODEL=nemotron)"
	@echo "                             llama_stack: Backend uses Llama Stack (use with MODEL=qwen3)"
	@echo "                             NOTE: Nemotron is incompatible with llama_stack mode"
	@echo "  model.storage.s3Bucket   - S3 bucket path (optional, overrides default OCI image for nemotron)"
	@echo "  model.storage.uri        - Custom OCI/URI path (optional, overrides default OCI image for nemotron)"
	@echo "  postgres.userId          - PostgreSQL user ID (required)"
	@echo "  postgres.password        - PostgreSQL password (required)"
	@echo "  postgres.databaseName    - PostgreSQL database name (required)"
	@echo "  minio.userId             - User ID to use for minio installation (required if DEPLOY_MINIO=true)"
	@echo "  minio.password           - Password to use for minio installation (required if DEPLOY_MINIO=true)"
	@echo "  pgadmin.email            - pgAdmin login email (required if DEPLOY_PGADMIN=true)"
	@echo "  pgadmin.password         - pgAdmin login password (required if DEPLOY_PGADMIN=true)"
	@echo "  pgairman.accessMode      - MCP access mode: restricted or unrestricted (default: restricted)"
	@echo "  llm.apiKey               - LLM API key (defaults from values.yaml, auto-extracted if DEPLOY_MODEL=true)"
	@echo "  llm.baseUrl              - LLM base URL (defaults from values.yaml, auto-extracted if DEPLOY_MODEL=true)"
	@echo "  llm.model                - LLM model name (defaults from values.yaml, auto-extracted if DEPLOY_MODEL=true)"
	@echo "  llm.maxContextLength - LLM max context length in tokens (default: 8096)"

# Older version of oc will raise error processing some of the commands in this make file; enforce a minimum version
.PHONY: check-oc-version
check-oc-version:
	$(eval USER_OC_VERSION = $(shell oc version --client=true -o json | jq -r .clientVersion.gitVersion))
	@echo "Detected oc version on your machine: $(USER_OC_VERSION)"
	@echo "NOTE: This install script has only been tested for oc version $(MINIMUM_OC_VERSION) and the bash and zsh shells."

# Minio internally rejects user id and password values less than 3 and 8 characters, respectively
# The install will fail if this occurs, so let's catch it early
.PHONY: check-minio-credentials
check-minio-credentials:
	@if [ -z "$(minio.userId)" ]; then \
		echo "Set minio.userId to a value that is at least $(MINIMUM_USERID_LENGTH) characters in length."; \
		exit 1; \
	fi
	@if [ $$(wc -m <<< $(minio.userId)) -lt $$(expr $(MINIMUM_USERID_LENGTH) + 1) ]; then \
		echo "Set minio.userId to a value that is at least $(MINIMUM_USERID_LENGTH) characters in length."; \
		exit 1; \
	fi
	@if [ -z "$(minio.password)" ]; then \
		echo "Set minio.password to a value that is at least $(MINIMUM_PASSWORD_LENGTH) characters in length."; \
		exit 1; \
	fi
	@if [ $$(wc -m <<< $(minio.password)) -lt $$(expr $(MINIMUM_PASSWORD_LENGTH) + 1) ]; then \
		echo "Set minio.password to a value that is at least $(MINIMUM_PASSWORD_LENGTH) characters in length."; \
		exit 1; \
	fi

.PHONY: check-postgres-credentials
check-postgres-credentials:
	@if [ -z "$(postgres.userId)" ]; then \
		echo "Error: postgres.userId must be set."; \
		exit 1; \
	fi
	@if [ -z "$(postgres.password)" ]; then \
		echo "Error: postgres.password must be set."; \
		exit 1; \
	fi
	@if [ -z "$(postgres.databaseName)" ]; then \
		echo "Error: postgres.databaseName must be set."; \
		exit 1; \
	fi

# Validation for pgAdmin credentials
.PHONY: check-pgadmin-credentials
check-pgadmin-credentials:
	@if [ -z "$(pgadmin.email)" ]; then \
		echo "Error: pgadmin.email must be set."; \
		exit 1; \
	fi
	@if [ -z "$(pgadmin.password)" ]; then \
		echo "Error: pgadmin.password must be set."; \
		exit 1; \
	fi

# Validation for LLM API key
.PHONY: check-llm-api-key
check-llm-api-key:
	@if [ -z "$(llm.apiKey)" ]; then \
		echo "Error: llm.apiKey must be set."; \
		echo "Usage: make copilot-backend-install NAMESPACE=... llm.apiKey=your-key"; \
		echo "Note: Use 'not-needed' for vLLM servers without authentication"; \
		exit 1; \
	fi

# Validation: Prevent Nemotron model with Llama Stack mode
.PHONY: check-model-provider-compatibility
check-model-provider-compatibility:
	@if [ "$(MODEL)" = "nemotron" ] && [ "$(PROVIDER_MODE)" = "llama_stack" ]; then \
		echo "Error: Nemotron model is not compatible with Llama Stack mode."; \
		echo "Nemotron uses custom <TOOLCALL> format which Llama Stack does not support."; \
		echo ""; \
		echo "Solutions:"; \
		echo "  1. Use PROVIDER_MODE=llama_stack with qwen3 (accessed via LiteLLM endpoint)"; \
		echo "  2. Use MODEL=nemotron with PROVIDER_MODE=mcp_direct"; \
		echo ""; \
		echo "Example: make install NAMESPACE=myns PROVIDER_MODE=llama_stack"; \
		exit 1; \
	fi

# Note: check-hf-token removed - no longer supporting local Llama model deployment

.PHONY: namespace
namespace:
	@oc create namespace $(NAMESPACE) &> /dev/null && oc label namespace $(NAMESPACE) modelmesh-enabled=false ||:
	@oc project $(NAMESPACE) &> /dev/null ||:

.PHONY: install
install: check-oc-version check-postgres-credentials check-model-provider-compatibility namespace
ifeq ($(DEPLOY_MINIO),true)
	@$(MAKE) check-minio-credentials
endif
ifeq ($(DEPLOY_PGADMIN),true)
	@$(MAKE) check-pgadmin-credentials
endif
ifeq ($(DEPLOY_MODEL),true)
	@echo "DEPLOY_MODEL=true: Starting $(MODEL) model deployment..."
ifeq ($(MODEL),nemotron)
	@$(MAKE) nemotron-model-deploy NAMESPACE=$(NAMESPACE) \
		$(if $(model.storage.s3Bucket),model.storage.s3Bucket=$(model.storage.s3Bucket),) \
		$(if $(model.storage.uri),model.storage.uri=$(model.storage.uri),)
else ifeq ($(MODEL),qwen3)
	@$(MAKE) qwen3-model-deploy NAMESPACE=$(NAMESPACE) \
		$(if $(model.storage.s3Bucket),model.storage.s3Bucket=$(model.storage.s3Bucket),) \
		$(if $(model.storage.uri),model.storage.uri=$(model.storage.uri),)
endif
	@echo "Model is deploying in the background. Continuing with remaining deployments..."
endif
ifeq ($(DEPLOY_MINIO),true)
	@$(MAKE) minio-install NAMESPACE=$(NAMESPACE)
else
	@echo "Skipping MinIO installation (DEPLOY_MINIO=$(DEPLOY_MINIO))"
endif
	@$(MAKE) database-install NAMESPACE=$(NAMESPACE)
ifeq ($(DEPLOY_PGADMIN),true)
	@$(MAKE) pgadmin-install NAMESPACE=$(NAMESPACE)
else
	@echo "Skipping pgAdmin installation (DEPLOY_PGADMIN=$(DEPLOY_PGADMIN))"
endif
	@$(MAKE) pg-airman-mcp-install NAMESPACE=$(NAMESPACE)
	@$(MAKE) copilot-llama-stack-install NAMESPACE=$(NAMESPACE) PROVIDER_MODE=$(PROVIDER_MODE) DEPLOY_MODEL=$(DEPLOY_MODEL) \
		$(if $(llm.model),llm.model=$(llm.model),) \
		$(if $(llm.baseUrl),llm.baseUrl=$(llm.baseUrl),) \
		$(if $(llm.apiKey),llm.apiKey=$(llm.apiKey),)
	@$(MAKE) copilot-backend-install NAMESPACE=$(NAMESPACE) DEPLOY_MODEL=$(DEPLOY_MODEL) \
		$(if $(model.storage.s3Bucket),model.storage.s3Bucket=$(model.storage.s3Bucket),) \
		$(if $(llm.baseUrl),llm.baseUrl=$(llm.baseUrl),) \
		$(if $(llm.model),llm.model=$(llm.model),) \
		$(if $(llm.apiKey),llm.apiKey=$(llm.apiKey),)
	@$(MAKE) copilot-ui-install NAMESPACE=$(NAMESPACE)

.PHONY: minio-install
minio-install:
	@echo "Installing Minio helm chart and default bucket ..."
	@helm -n $(NAMESPACE) upgrade --install minio $(MINIO_CHART) \
		--set minio.userId=$(minio.userId) \
		--set minio.password=$(minio.password) \
		--timeout 5m
	@echo "Waiting for Minio route 'minio-api' to become ready in namespace $(NAMESPACE)..."
	@oc wait pod -l app=minio -n $(NAMESPACE) --for=condition=Ready --timeout=60s
	@oc wait --for=jsonpath='{.status.ingress[0].conditions[?(@.type=="Admitted")].status}=True' \
		route/minio-api -n $(NAMESPACE) --timeout=60s
	@echo "Minio installation complete."

.PHONY: build-data-loader-image
build-data-loader-image:
	@echo "Creating ImageStream for data loader..."
	@oc create imagestream pgvector-data-loader -n $(NAMESPACE) 2>/dev/null || echo "ImageStream already exists"
	@echo "Creating/updating BuildConfig for data loader..."
	@oc apply -f $(POSTGRES_CHART)/buildconfig.yaml -n $(NAMESPACE)
	@echo "Starting binary build (uploading CSV files and scripts to OpenShift)..."
	@echo "This will upload ~45MB of data files..."
	@cd $(POSTGRES_CHART) && oc start-build pgvector-data-loader --from-dir=. --follow -n $(NAMESPACE)
	@echo "Data loader image built successfully in OpenShift internal registry"

.PHONY: database-install
database-install: build-data-loader-image
	@echo "Installing, configuring and loading Postgres database ..."
	@helm -n $(NAMESPACE) upgrade --install postgres $(POSTGRES_CHART) \
		--set postgres.userId=$(postgres.userId) \
		--set postgres.password=$(postgres.password) \
		--set postgres.databaseName=$(postgres.databaseName) \
		--timeout 10m
	@echo "Waiting for data loading job to complete..."
	@oc wait --for=condition=complete --timeout=600s job/pgvector-data-loader -n $(NAMESPACE) || \
		(echo "Data loading job failed or timed out. Check logs with: oc logs job/pgvector-data-loader -n $(NAMESPACE)" && exit 1)
	@echo "Database installation and data loading complete."

# Install pgAdmin for database administration
.PHONY: pgadmin-install
pgadmin-install:
	@echo "Pre-creating pgadmin service account and granting privileged SCC..."
	@oc create serviceaccount pgadmin -n $(NAMESPACE) 2>/dev/null || echo "ServiceAccount already exists"
	@oc adm policy add-scc-to-user privileged -z pgadmin -n $(NAMESPACE) 2>/dev/null || echo "SCC already granted"
	@echo "Installing pgAdmin helm chart..."
	@helm -n $(NAMESPACE) upgrade --install pgadmin $(PGADMIN_CHART) \
		--set pgadmin.email=$(pgadmin.email) \
		--set pgadmin.password=$(pgadmin.password) \
		--set postgres.host=pgvector-0.pgvector-postgres-service \
		--set postgres.port=5432 \
		--set postgres.user=$(postgres.userId) \
		--set postgres.password=$(postgres.password) \
		--set postgres.database=$(postgres.databaseName) \
		--timeout 5m
	@echo "Waiting for pgAdmin to be ready..."
	@oc rollout status deployment/pgadmin -n $(NAMESPACE) --timeout=180s
	@echo "Waiting for pgAdmin route to be ready..."
	@oc wait --for=jsonpath='{.status.ingress[0].conditions[?(@.type=="Admitted")].status}=True' \
		route/pgadmin -n $(NAMESPACE) --timeout=60s
	@echo "pgAdmin installation complete."
	@echo "pgAdmin URL: https://$$(oc get route pgadmin -o jsonpath='{.spec.host}' -n $(NAMESPACE))"
	@echo "Login with email: $(pgadmin.email)"

# Build pg-airman-mcp custom image with libpq5 fix
.PHONY: build-pg-airman-mcp-image
build-pg-airman-mcp-image:
	@echo "Creating ImageStream for pg-airman-mcp..."
	@oc apply -f $(PG_AIRMAN_MCP_CHART)/imagestream.yaml -n $(NAMESPACE)
	@echo "Creating BuildConfig for pg-airman-mcp..."
	@oc apply -f $(PG_AIRMAN_MCP_CHART)/buildconfig.yaml -n $(NAMESPACE)
	@echo "Starting image build (this may take 5-10 minutes)..."
	@oc start-build pg-airman-mcp --follow -n $(NAMESPACE) || echo "Build already running or completed"
	@echo "pg-airman-mcp image built successfully"

# Install pg-airman-mcp MCP server
.PHONY: pg-airman-mcp-install
pg-airman-mcp-install: check-postgres-credentials build-pg-airman-mcp-image
	@echo "Installing pg-airman-mcp helm chart..."
ifeq ($(PROVIDER_MODE),llama_stack)
	@echo "PROVIDER_MODE=llama_stack: Using SSE transport for Llama Stack compatibility"
	@helm -n $(NAMESPACE) upgrade --install pg-airman-mcp $(PG_AIRMAN_MCP_CHART) \
		--set image.repository=image-registry.openshift-image-registry.svc:5000/$(NAMESPACE)/pg-airman-mcp \
		--set image.tag=latest \
		--set image.pullPolicy=Always \
		--set postgres.host=pgvector-0.pgvector-postgres-service \
		--set postgres.port=5432 \
		--set postgres.user=$(postgres.userId) \
		--set postgres.password=$(postgres.password) \
		--set postgres.database=$(postgres.databaseName) \
		--set mcp.transport=sse \
		--set mcp.accessMode=$(if $(pgairman.accessMode),$(pgairman.accessMode),restricted) \
		--timeout 5m
	@echo "Waiting for pg-airman-mcp to be ready..."
	@oc rollout status deployment/pg-airman-mcp -n $(NAMESPACE) --timeout=300s
	@echo "pg-airman-mcp installation complete."
	@echo "Service URL (internal): http://pg-airman-mcp-service:8000"
	@echo "Transport: sse (for Llama Stack), access mode: $(if $(pgairman.accessMode),$(pgairman.accessMode),restricted)"
else
	@echo "Using streamable-http transport (default)"
	@helm -n $(NAMESPACE) upgrade --install pg-airman-mcp $(PG_AIRMAN_MCP_CHART) \
		--set image.repository=image-registry.openshift-image-registry.svc:5000/$(NAMESPACE)/pg-airman-mcp \
		--set image.tag=latest \
		--set image.pullPolicy=Always \
		--set postgres.host=pgvector-0.pgvector-postgres-service \
		--set postgres.port=5432 \
		--set postgres.user=$(postgres.userId) \
		--set postgres.password=$(postgres.password) \
		--set postgres.database=$(postgres.databaseName) \
		--set mcp.accessMode=$(if $(pgairman.accessMode),$(pgairman.accessMode),restricted) \
		--timeout 5m
	@echo "Waiting for pg-airman-mcp to be ready..."
	@oc rollout status deployment/pg-airman-mcp -n $(NAMESPACE) --timeout=300s
	@echo "pg-airman-mcp installation complete."
	@echo "Service URL (internal): http://pg-airman-mcp-service:8000"
	@echo "Transport: streamable-http (default), access mode: $(if $(pgairman.accessMode),$(pgairman.accessMode),restricted)"
endif

.PHONY: uninstall
uninstall: check-oc-version minio-uninstall database-uninstall pgadmin-uninstall pg-airman-mcp-uninstall nemotron-model-uninstall qwen3-model-uninstall copilot-llama-stack-uninstall copilot-backend-uninstall copilot-ui-uninstall delete-project

.PHONY: minio-uninstall
minio-uninstall:
	@echo "Uninstalling Minio helm chart"
	@helm -n $(NAMESPACE) uninstall minio || true
	@echo "Removing minio PVCs from $(NAMESPACE)"
	@oc get pvc -n $(NAMESPACE) -o custom-columns=NAME:.metadata.name | grep -E '^(minio)-data' | xargs -I {} oc delete pvc -n $(NAMESPACE) {} ||:

.PHONY: database-uninstall
database-uninstall:
	@echo "Uninstalling Postgres helm chart"
	@helm -n $(NAMESPACE) uninstall postgres || true
	@echo "Removing Postgres PVCs from $(NAMESPACE)"
	@oc get pvc -n $(NAMESPACE) -o custom-columns=NAME:.metadata.name | grep -E '^(pgvector)-data' | xargs -I {} oc delete pvc -n $(NAMESPACE) {} ||:

# Uninstall pgAdmin
.PHONY: pgadmin-uninstall
pgadmin-uninstall:
	@echo "Uninstalling pgAdmin helm chart"
	@helm -n $(NAMESPACE) uninstall pgadmin || true
	@echo "Removing pgAdmin PVCs from $(NAMESPACE)"
	@oc get pvc -n $(NAMESPACE) -o custom-columns=NAME:.metadata.name | grep -E '^(pgadmin)-data' | xargs -I {} oc delete pvc -n $(NAMESPACE) {} ||:

# Uninstall pg-airman-mcp
.PHONY: pg-airman-mcp-uninstall
pg-airman-mcp-uninstall:
	@echo "Uninstalling pg-airman-mcp helm chart"
	@helm -n $(NAMESPACE) uninstall pg-airman-mcp || true

# Deploy NVIDIA Nemotron model using KServe (non-blocking - just starts deployment)
.PHONY: nemotron-model-deploy
nemotron-model-deploy:
	@echo "Deploying NVIDIA Nemotron Nano 9B v2 model using KServe..."
	@echo "Using OCI container image: quay.io/eformat/nvidia-nemotron-nano-9b-v2"
	@helm -n $(NAMESPACE) upgrade --install nemotron-model $(NEMOTRON_MODEL_CHART) \
		$(if $(model.storage.s3Bucket),--set model.storage.type=s3 --set model.storage.s3Bucket=$(model.storage.s3Bucket),) \
		$(if $(model.storage.uri),--set model.storage.uri=$(model.storage.uri),) \
		--timeout 10m
	@echo "Model deployment started. It will be ready in 5-10 minutes."
	@echo "You can monitor progress with: oc get inferenceservice nvidia-nemotron-nano-9b-v2 -n $(NAMESPACE) -w"

# Wait for NVIDIA Nemotron model to be ready
.PHONY: nemotron-model-wait
nemotron-model-wait:
	@echo "Waiting for InferenceService to be ready (this may take 5-10 minutes for model download)..."
	@bash -c 'start_time=$$(date +%s); \
		while true; do \
			if oc get inferenceservice nvidia-nemotron-nano-9b-v2 -n $(NAMESPACE) -o jsonpath="{.status.conditions[?(@.type==\"Ready\")].status}" 2>/dev/null | grep -q "True"; then \
				break; \
			fi; \
			elapsed=$$(($$(date +%s) - start_time)); \
			if [ $$elapsed -gt 600 ]; then \
				echo "Timeout waiting for model deployment. Check status with: oc get inferenceservice nvidia-nemotron-nano-9b-v2 -n $(NAMESPACE)"; \
				exit 1; \
			fi; \
			echo "Waiting for model to be ready... ($$elapsed seconds elapsed)"; \
			sleep 10; \
		done'
	@echo "Model deployment complete!"
	@echo "Model endpoint: https://$$(oc get route nvidia-nemotron-nano-9b-v2 -o jsonpath='{.spec.host}' -n $(NAMESPACE))"

# Deploy and wait for NVIDIA Nemotron model (convenience target)
.PHONY: nemotron-model-install
nemotron-model-install: nemotron-model-deploy nemotron-model-wait

# Uninstall nemotron-model
.PHONY: nemotron-model-uninstall
nemotron-model-uninstall:
	@echo "Uninstalling nemotron-model helm chart"
	@helm -n $(NAMESPACE) uninstall nemotron-model || true

# Deploy Qwen3-14B model using KServe (non-blocking - just starts deployment)
.PHONY: qwen3-model-deploy
qwen3-model-deploy:
	@echo "Deploying Qwen3-14B model using KServe..."
	@echo "Using HuggingFace model: hf://Qwen/Qwen3-14B"
	@helm -n $(NAMESPACE) upgrade --install qwen3-model $(QWEN3_MODEL_CHART) \
		$(if $(model.storage.s3Bucket),--set model.storage.type=s3 --set model.storage.s3Bucket=$(model.storage.s3Bucket),) \
		$(if $(model.storage.uri),--set model.storage.uri=$(model.storage.uri),) \
		--timeout 15m
	@echo "Model deployment started. It will be ready in 10-15 minutes (Qwen3-14B is larger than Nemotron)."
	@echo "You can monitor progress with: oc get inferenceservice qwen3-14b -n $(NAMESPACE) -w"

# Wait for Qwen3-14B model to be ready
.PHONY: qwen3-model-wait
qwen3-model-wait:
	@echo "Waiting for InferenceService to be ready (this may take 10-15 minutes for model download)..."
	@bash -c 'start_time=$$(date +%s); \
		while true; do \
			if oc get inferenceservice qwen3-14b -n $(NAMESPACE) -o jsonpath="{.status.conditions[?(@.type==\"Ready\")].status}" 2>/dev/null | grep -q "True"; then \
				break; \
			fi; \
			elapsed=$$(($$(date +%s) - start_time)); \
			if [ $$elapsed -gt 900 ]; then \
				echo "Timeout waiting for model deployment. Check status with: oc get inferenceservice qwen3-14b -n $(NAMESPACE)"; \
				exit 1; \
			fi; \
			echo "Waiting for model to be ready... ($$elapsed seconds elapsed)"; \
			sleep 15; \
		done'
	@echo "Model deployment complete!"
	@echo "Model endpoint: https://$$(oc get route qwen3-14b -o jsonpath='{.spec.host}' -n $(NAMESPACE))"

# Deploy and wait for Qwen3-14B model (convenience target)
.PHONY: qwen3-model-install
qwen3-model-install: qwen3-model-deploy qwen3-model-wait

# Uninstall qwen3-model
.PHONY: qwen3-model-uninstall
qwen3-model-uninstall:
	@echo "Uninstalling qwen3-model helm chart"
	@helm -n $(NAMESPACE) uninstall qwen3-model || true

# Build copilot-backend custom image
.PHONY: build-copilot-backend-image
build-copilot-backend-image:
	@echo "Creating ImageStream for copilot-backend..."
	@oc apply -f $(COPILOT_BACKEND_CHART)/imagestream.yaml -n $(NAMESPACE)
	@echo "Creating BuildConfig for copilot-backend..."
	@oc apply -f $(COPILOT_BACKEND_CHART)/buildconfig.yaml -n $(NAMESPACE)
	@echo "Starting image build (this may take 3-5 minutes)..."
	@echo "Uploading source files to OpenShift..."
	@oc start-build copilot-backend --from-dir=.. --follow -n $(NAMESPACE) || echo "Build already running or completed"
	@echo "copilot-backend image built successfully"

# Install copilot-backend service
.PHONY: copilot-backend-install
copilot-backend-install: build-copilot-backend-image
ifeq ($(DEPLOY_MODEL),true)
	@echo "DEPLOY_MODEL=true: Waiting for $(MODEL) model to be ready..."
ifeq ($(MODEL),nemotron)
	@$(MAKE) nemotron-model-wait NAMESPACE=$(NAMESPACE)
	@echo "Extracting nemotron model configuration from deployment..."
	@MODEL_NAME=$$(oc get inferenceservice -n $(NAMESPACE) -l release=nemotron-model -o jsonpath='{.items[0].metadata.name}'); \
	MODEL_URL="https://$$(oc get route $$MODEL_NAME -o jsonpath='{.spec.host}' -n $(NAMESPACE))/v1"; \
	MODEL_API_KEY=$$(oc get secret default-name-$$MODEL_NAME-sa -n $(NAMESPACE) -o jsonpath='{.data.token}' | base64 -d); \
	echo "Model name: $$MODEL_NAME"; \
	echo "Model endpoint: $$MODEL_URL"; \
	echo "Model API key: [extracted from service account token secret]"; \
	if [ "$(PROVIDER_MODE)" = "llama_stack" ]; then \
		echo "ERROR: Nemotron model is incompatible with llama_stack mode. Use PROVIDER_MODE=mcp_direct for nemotron."; \
		exit 1; \
	else \
		echo "Installing copilot-backend in mcp_direct mode with nemotron model settings..."; \
		helm -n $(NAMESPACE) upgrade --install copilot-backend $(COPILOT_BACKEND_CHART) \
			--set image.repository=image-registry.openshift-image-registry.svc:5000/$(NAMESPACE)/copilot-backend \
			--set image.tag=latest \
			--set image.pullPolicy=Always \
			--set provider.mode=$(PROVIDER_MODE) \
			--set llm.baseUrl=$$MODEL_URL \
			--set llm.model=$$MODEL_NAME \
			--set llm.apiKey=$$MODEL_API_KEY \
			$(if $(llm.maxContextLength),--set llm.maxContextLength=$(llm.maxContextLength),) \
			--timeout 5m; \
	fi
else ifeq ($(MODEL),qwen3)
	@$(MAKE) qwen3-model-wait NAMESPACE=$(NAMESPACE)
	@echo "Extracting qwen3 model configuration from deployment..."
	@MODEL_NAME=$$(oc get inferenceservice -n $(NAMESPACE) -l release=qwen3-model -o jsonpath='{.items[0].metadata.name}'); \
	MODEL_URL="https://$$(oc get route $$MODEL_NAME -o jsonpath='{.spec.host}' -n $(NAMESPACE))/v1"; \
	MODEL_API_KEY=$$(oc get secret default-name-$$MODEL_NAME-sa -n $(NAMESPACE) -o jsonpath='{.data.token}' | base64 -d); \
	echo "Model name: $$MODEL_NAME"; \
	echo "Model endpoint: $$MODEL_URL"; \
	echo "Model API key: [extracted from service account token secret]"; \
	if [ "$(PROVIDER_MODE)" = "llama_stack" ]; then \
		echo "Installing copilot-backend in llama_stack mode with qwen3 model settings..."; \
		LLAMA_STACK_URL="http://$(LLAMA_STACK_DISTRIBUTION_NAME)-service:$(LLAMA_STACK_SERVICE_PORT)"; \
		helm -n $(NAMESPACE) upgrade --install copilot-backend $(COPILOT_BACKEND_CHART) \
			--set image.repository=image-registry.openshift-image-registry.svc:5000/$(NAMESPACE)/copilot-backend \
			--set image.tag=latest \
			--set image.pullPolicy=Always \
			--set provider.mode=$(PROVIDER_MODE) \
			--set llamaStack.baseUrl=$$LLAMA_STACK_URL \
			--set llm.baseUrl=$$MODEL_URL \
			--set llm.model=$$MODEL_NAME \
			--set llm.apiKey=$$MODEL_API_KEY \
			$(if $(llm.maxContextLength),--set llm.maxContextLength=$(llm.maxContextLength),) \
			--timeout 5m; \
	else \
		echo "Installing copilot-backend in mcp_direct mode with qwen3 model settings..."; \
		helm -n $(NAMESPACE) upgrade --install copilot-backend $(COPILOT_BACKEND_CHART) \
			--set image.repository=image-registry.openshift-image-registry.svc:5000/$(NAMESPACE)/copilot-backend \
			--set image.tag=latest \
			--set image.pullPolicy=Always \
			--set provider.mode=$(PROVIDER_MODE) \
			--set llm.baseUrl=$$MODEL_URL \
			--set llm.model=$$MODEL_NAME \
			--set llm.apiKey=$$MODEL_API_KEY \
			$(if $(llm.maxContextLength),--set llm.maxContextLength=$(llm.maxContextLength),) \
			--timeout 5m; \
	fi
endif
else
	@echo "Installing copilot-backend with configured model endpoint..."
	@if [ "$(PROVIDER_MODE)" = "llama_stack" ]; then \
		echo "Installing copilot-backend in llama_stack mode..."; \
		LLAMA_STACK_URL="http://$(LLAMA_STACK_DISTRIBUTION_NAME)-service:$(LLAMA_STACK_SERVICE_PORT)"; \
		echo "Llama Stack URL: $$LLAMA_STACK_URL"; \
		helm -n $(NAMESPACE) upgrade --install copilot-backend $(COPILOT_BACKEND_CHART) \
			--set image.repository=image-registry.openshift-image-registry.svc:5000/$(NAMESPACE)/copilot-backend \
			--set image.tag=latest \
			--set image.pullPolicy=Always \
			--set provider.mode=$(PROVIDER_MODE) \
			--set llamaStack.baseUrl=$$LLAMA_STACK_URL \
			$(if $(llm.baseUrl),--set llm.baseUrl=$(llm.baseUrl),) \
			$(if $(llm.model),--set llm.model=$(llm.model),) \
			$(if $(llm.apiKey),--set llm.apiKey=$(llm.apiKey),) \
			$(if $(llm.maxContextLength),--set llm.maxContextLength=$(llm.maxContextLength),) \
			--timeout 5m; \
	else \
		echo "Installing copilot-backend in mcp_direct mode..."; \
		helm -n $(NAMESPACE) upgrade --install copilot-backend $(COPILOT_BACKEND_CHART) \
			--set image.repository=image-registry.openshift-image-registry.svc:5000/$(NAMESPACE)/copilot-backend \
			--set image.tag=latest \
			--set image.pullPolicy=Always \
			--set provider.mode=$(PROVIDER_MODE) \
			$(if $(llm.baseUrl),--set llm.baseUrl=$(llm.baseUrl),) \
			$(if $(llm.model),--set llm.model=$(llm.model),) \
			$(if $(llm.apiKey),--set llm.apiKey=$(llm.apiKey),) \
			$(if $(llm.maxContextLength),--set llm.maxContextLength=$(llm.maxContextLength),) \
			--timeout 5m; \
	fi
endif
	@echo "Waiting for copilot-backend to be ready..."
	@oc rollout status deployment/copilot-backend -n $(NAMESPACE) --timeout=300s
	@echo "copilot-backend installation complete."
	@echo "Service URL (internal): http://copilot-backend:8080"
	@echo "Public route: https://$$(oc get route copilot-backend -o jsonpath='{.spec.host}' -n $(NAMESPACE))"

# Uninstall copilot-backend
.PHONY: copilot-backend-uninstall
copilot-backend-uninstall:
	@echo "Uninstalling copilot-backend helm chart"
	@helm -n $(NAMESPACE) uninstall copilot-backend || true

# Install Llama Stack distribution (conditional on PROVIDER_MODE)
.PHONY: copilot-llama-stack-install
copilot-llama-stack-install: check-model-provider-compatibility
ifeq ($(PROVIDER_MODE),llama_stack)
	@echo "DEBUG: DEPLOY_MODEL=$(DEPLOY_MODEL), MODEL=$(MODEL)"
ifeq ($(DEPLOY_MODEL),true)
	@echo "DEPLOY_MODEL=true: Waiting for $(MODEL) model to be ready before configuring Llama Stack..."
ifeq ($(MODEL),qwen3)
	@$(MAKE) qwen3-model-wait NAMESPACE=$(NAMESPACE)
	@echo "Extracting qwen3 model configuration for Llama Stack..."
	@MODEL_NAME=$$(oc get inferenceservice -n $(NAMESPACE) -l release=qwen3-model -o jsonpath='{.items[0].metadata.name}'); \
	if [ -z "$$MODEL_NAME" ]; then \
		echo "ERROR: No InferenceService found with label release=qwen3-model in namespace $(NAMESPACE)"; \
		echo "Cannot extract model configuration. Please ensure DEPLOY_MODEL=true actually deployed the model."; \
		exit 1; \
	fi; \
	MODEL_URL="https://$$(oc get route $$MODEL_NAME -o jsonpath='{.spec.host}' -n $(NAMESPACE))/v1"; \
	MODEL_API_KEY=$$(oc get secret default-name-$$MODEL_NAME-sa -n $(NAMESPACE) -o jsonpath='{.data.token}' | base64 -d); \
	echo "Model name: $$MODEL_NAME"; \
	echo "Model URL: $$MODEL_URL"; \
	echo "Model API key: [extracted from service account token secret]"; \
	echo "Installing Llama Stack with deployed Qwen3 model..."; \
	helm -n $(NAMESPACE) upgrade --install $(LLAMA_STACK_DISTRIBUTION_NAME) $(COPILOT_LLAMA_STACK_CHART) \
		--set distribution.name=$(LLAMA_STACK_DISTRIBUTION_NAME) \
		--set container.port=$(LLAMA_STACK_SERVICE_PORT) \
		--set model.name=$$MODEL_NAME \
		--set model.url=$$MODEL_URL \
		--set model.apiKey=$$MODEL_API_KEY \
		--timeout 10m
else
	@echo "ERROR: DEPLOY_MODEL=true with llama_stack mode requires MODEL=qwen3"
	@echo "Nemotron cannot be used with Llama Stack."
	@exit 1
endif
else
	@echo "Installing Llama Stack with external model endpoint..."
	@LLAMA_STACK_BASE_URL="$(llm.baseUrl)"; \
	if [ -z "$$LLAMA_STACK_BASE_URL" ]; then \
		LLAMA_STACK_BASE_URL=$$(yq e '.llm.baseUrl' $(COPILOT_BACKEND_CHART)/values.yaml); \
	fi; \
	LLAMA_STACK_MODEL="$(llm.model)"; \
	if [ -z "$$LLAMA_STACK_MODEL" ]; then \
		LLAMA_STACK_MODEL=$$(yq e '.llm.model' $(COPILOT_BACKEND_CHART)/values.yaml); \
	fi; \
	LLAMA_STACK_API_KEY="$(llm.apiKey)"; \
	echo "Using baseUrl: $$LLAMA_STACK_BASE_URL"; \
	echo "Using model: $$LLAMA_STACK_MODEL"; \
	echo "Using API key: $${LLAMA_STACK_API_KEY:+[provided]}$${LLAMA_STACK_API_KEY:-[not provided]}"; \
	if [ -z "$$LLAMA_STACK_BASE_URL" ] || [ -z "$$LLAMA_STACK_MODEL" ]; then \
		echo "ERROR: Missing required configuration for external model:"; \
		echo "  baseUrl: $$LLAMA_STACK_BASE_URL"; \
		echo "  model: $$LLAMA_STACK_MODEL"; \
		echo "Please set llm.baseUrl and llm.model, or configure them in copilot-backend/values.yaml (llm section)"; \
		exit 1; \
	fi; \
	helm -n $(NAMESPACE) upgrade --install $(LLAMA_STACK_DISTRIBUTION_NAME) $(COPILOT_LLAMA_STACK_CHART) \
		--set distribution.name=$(LLAMA_STACK_DISTRIBUTION_NAME) \
		--set container.port=$(LLAMA_STACK_SERVICE_PORT) \
		--set model.name=$$LLAMA_STACK_MODEL \
		--set model.url=$$LLAMA_STACK_BASE_URL \
		$(if $(llm.apiKey),--set model.apiKey=$(llm.apiKey),) \
		--timeout 10m
endif
	@echo "Waiting for Llama Stack to be ready..."
	@sleep 10
	@oc wait --for=jsonpath='{.status.conditions[?(@.type=="DeploymentReady")].status}=True' \
		llamastackdistribution/$(LLAMA_STACK_DISTRIBUTION_NAME) -n $(NAMESPACE) --timeout=600s || \
		(echo "Llama Stack deployment failed. Check logs with: oc logs -l app.kubernetes.io/name=$(LLAMA_STACK_DISTRIBUTION_NAME) -n $(NAMESPACE)" && exit 1)
	@echo "Llama Stack installation complete."
	@echo "Service URL (internal): http://$(LLAMA_STACK_DISTRIBUTION_NAME)-service:$(LLAMA_STACK_SERVICE_PORT)"
	@echo "Public route: https://$$(oc get route llama-stack-api -o jsonpath='{.spec.host}' -n $(NAMESPACE))"
else
	@echo "Skipping Llama Stack installation (PROVIDER_MODE=$(PROVIDER_MODE))"
endif

# Uninstall Llama Stack distribution
.PHONY: copilot-llama-stack-uninstall
copilot-llama-stack-uninstall:
	@echo "Uninstalling Llama Stack helm chart"
	@-helm -n $(NAMESPACE) uninstall $(LLAMA_STACK_DISTRIBUTION_NAME) 2>/dev/null || echo "Llama Stack chart not installed"
	@echo "Cleaning up Llama Stack PVCs (if any)..."
	@-oc get pvc -n $(NAMESPACE) -o json | \
		jq -r '.items[] | select(.metadata.ownerReferences[]?.name | contains("$(LLAMA_STACK_DISTRIBUTION_NAME)")) | .metadata.name' | \
		xargs -I {} oc delete pvc {} -n $(NAMESPACE) 2>/dev/null || echo "No Llama Stack PVCs found"

# Build copilot-ui custom image
.PHONY: build-copilot-ui-image
build-copilot-ui-image:
	@echo "Creating ImageStream for copilot-ui..."
	@oc apply -f $(COPILOT_UI_CHART)/imagestream.yaml -n $(NAMESPACE)
	@echo "Creating BuildConfig for copilot-ui..."
	@oc apply -f $(COPILOT_UI_CHART)/buildconfig.yaml -n $(NAMESPACE)
	@echo "Starting image build (this may take 3-5 minutes)..."
	@echo "Uploading UI source files to OpenShift..."
	@oc start-build copilot-ui --from-dir=../. --follow -n $(NAMESPACE) || echo "Build already running or completed"
	@echo "copilot-ui image built successfully"
	@echo "Note: Backend URL will be configured at runtime via COPILOT_BACKEND_URL env var"

# Install copilot-ui frontend
.PHONY: copilot-ui-install
copilot-ui-install: build-copilot-ui-image
	@echo "Installing copilot-ui helm chart..."
	@BACKEND_URL=$$(oc get route copilot-backend -o jsonpath='https://{.spec.host}' -n $(NAMESPACE) 2>/dev/null || echo "http://copilot-backend:8080"); \
	helm -n $(NAMESPACE) upgrade --install copilot-ui $(COPILOT_UI_CHART) \
		--set image.repository=image-registry.openshift-image-registry.svc:5000/$(NAMESPACE)/copilot-ui \
		--set image.tag=latest \
		--set image.pullPolicy=Always \
		--set backend.url=$$BACKEND_URL \
		--timeout 5m
	@echo "Waiting for copilot-ui to be ready..."
	@oc rollout status deployment/copilot-ui -n $(NAMESPACE) --timeout=300s
	@echo "copilot-ui installation complete."
	@echo "Service URL (internal): http://copilot-ui:8080"
	@echo "Public UI URL: https://$$(oc get route copilot-ui -o jsonpath='{.spec.host}' -n $(NAMESPACE))"

# Uninstall copilot-ui
.PHONY: copilot-ui-uninstall
copilot-ui-uninstall:
	@echo "Uninstalling copilot-ui helm chart"
	@helm -n $(NAMESPACE) uninstall copilot-ui || true

.PHONY: delete-project
delete-project:
	@echo "Attempting to delete OpenShift project $(NAMESPACE)..."
	@oc delete project $(NAMESPACE)

