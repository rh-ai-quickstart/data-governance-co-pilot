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
# copilot-backend chart for FastAPI backend service
COPILOT_BACKEND_CHART := copilot-backend
# copilot-ui chart for Svelte frontend
COPILOT_UI_CHART := copilot-ui

# Flag to control whether to deploy the LLM model (default: false)
# Set to true to automatically deploy NVIDIA Nemotron model
DEPLOY_MODEL ?= false

MINIMUM_OC_VERSION = "4.17.0"
MINIMUM_USERID_LENGTH = 3
MINIMUM_PASSWORD_LENGTH = 8

# Default target
.PHONY: help
help:
	@echo "Available targets:"
	@echo "  install       - Installs quickstart and supporting resources"
	@echo "                  Required: NAMESPACE, postgres.userId, postgres.password, postgres.databaseName, minio.userId, minio.password, pgadmin.email, pgadmin.password"
	@echo "                  Optional: DEPLOY_MODEL=true (auto-configures model using OCI image)"
	@echo "                  Example: make install NAMESPACE=myns postgres.userId=postgres postgres.password=pass123 postgres.databaseName=recsys minio.userId=minio minio.password=minio123 pgadmin.email=admin@example.com pgadmin.password=admin123 DEPLOY_MODEL=true"
	@echo "  pg-airman-mcp-install - Installs pg-airman-mcp MCP server (builds custom image with libpq5 fix)"
	@echo "                  Required: NAMESPACE, postgres.userId, postgres.password, postgres.databaseName"
	@echo "                  Optional: pgairman.accessMode (default: restricted)"
	@echo "                  Note: First run builds custom image (5-10 minutes), subsequent runs are faster"
	@echo "  nemotron-model-install - Deploys NVIDIA Nemotron Nano 9B v2 model using KServe"
	@echo "                  Required: NAMESPACE"
	@echo "                  Optional: model.storage.s3Bucket (uses OCI container image by default)"
	@echo "                  Example: make nemotron-model-install NAMESPACE=myns"
	@echo "                  Note: Uses quay.io/eformat/nvidia-nemotron-nano-9b-v2 OCI image by default"
	@echo "  copilot-backend-install - Installs copilot backend service (FastAPI orchestration layer)"
	@echo "                  Required: NAMESPACE"
	@echo "                  Optional: DEPLOY_MODEL=true (auto-extracts llmBaseUrl, llmModel, and llmApiKey from deployed model)"
	@echo "                  If DEPLOY_MODEL=false: copilot.llmBaseUrl, copilot.llmModel, copilot.llmApiKey are required"
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
	@echo "                             Uses OCI image by default, model name/endpoint/API key auto-extracted"
	@echo "  model.storage.s3Bucket   - S3 bucket path (optional, overrides default OCI image)"
	@echo "  model.storage.uri        - Custom OCI/URI path (optional, overrides default OCI image)"
	@echo "  postgres.userId          - PostgreSQL user ID (required)"
	@echo "  postgres.password        - PostgreSQL password (required)"
	@echo "  postgres.databaseName    - PostgreSQL database name (required)"
	@echo "  minio.userId             - User ID to use for minio installation (required)"
	@echo "  minio.password           - Password to use for minio installation (required)"
	@echo "  pgadmin.email            - pgAdmin login email (required)"
	@echo "  pgadmin.password         - pgAdmin login password (required)"
	@echo "  pgairman.accessMode      - MCP access mode: restricted or unrestricted (default: restricted)"
	@echo "  copilot.llmApiKey        - LLM API key (required if DEPLOY_MODEL=false, auto-extracted if true)"
	@echo "  copilot.llmBaseUrl       - LLM base URL (required if DEPLOY_MODEL=false, auto-extracted if true)"
	@echo "  copilot.llmModel         - LLM model name (required if DEPLOY_MODEL=false, auto-extracted if true)"
	@echo "  copilot.maxContextLength - LLM max context length in tokens (default: 8096)"

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
	@if [ -z "$(copilot.llmApiKey)" ]; then \
		echo "Error: copilot.llmApiKey must be set."; \
		echo "Usage: make copilot-backend-install NAMESPACE=... copilot.llmApiKey=your-key"; \
		echo "Note: Use 'not-needed' for vLLM servers without authentication"; \
		exit 1; \
	fi

.PHONY: namespace
namespace:
	@oc create namespace $(NAMESPACE) &> /dev/null && oc label namespace $(NAMESPACE) modelmesh-enabled=false ||:
	@oc project $(NAMESPACE) &> /dev/null ||:

.PHONY: install
install: check-oc-version check-minio-credentials check-postgres-credentials check-pgadmin-credentials namespace
ifeq ($(DEPLOY_MODEL),true)
	@echo "DEPLOY_MODEL=true: Starting model deployment first (non-blocking)..."
	@$(MAKE) nemotron-model-deploy NAMESPACE=$(NAMESPACE) \
		$(if $(model.storage.s3Bucket),model.storage.s3Bucket=$(model.storage.s3Bucket),) \
		$(if $(model.storage.uri),model.storage.uri=$(model.storage.uri),)
	@echo "Model is deploying in the background. Continuing with remaining deployments..."
endif
	@$(MAKE) minio-install NAMESPACE=$(NAMESPACE)
	@$(MAKE) database-install NAMESPACE=$(NAMESPACE)
	@$(MAKE) pgadmin-install NAMESPACE=$(NAMESPACE)
	@$(MAKE) pg-airman-mcp-install NAMESPACE=$(NAMESPACE)
	@$(MAKE) copilot-backend-install NAMESPACE=$(NAMESPACE) DEPLOY_MODEL=$(DEPLOY_MODEL) \
		$(if $(model.storage.s3Bucket),model.storage.s3Bucket=$(model.storage.s3Bucket),) \
		$(if $(copilot.llmBaseUrl),copilot.llmBaseUrl=$(copilot.llmBaseUrl),) \
		$(if $(copilot.llmModel),copilot.llmModel=$(copilot.llmModel),) \
		$(if $(copilot.llmApiKey),copilot.llmApiKey=$(copilot.llmApiKey),)
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

.PHONY: uninstall
uninstall: check-oc-version minio-uninstall database-uninstall pgadmin-uninstall pg-airman-mcp-uninstall nemotron-model-uninstall copilot-backend-uninstall copilot-ui-uninstall delete-project

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
	@echo "DEPLOY_MODEL=true: Waiting for LLM model to be ready..."
	@$(MAKE) nemotron-model-wait NAMESPACE=$(NAMESPACE)
	@echo "Extracting model configuration from deployment..."
	@MODEL_NAME=$$(oc get inferenceservice -n $(NAMESPACE) -l release=nemotron-model -o jsonpath='{.items[0].metadata.name}'); \
	MODEL_URL="https://$$(oc get route $$MODEL_NAME -o jsonpath='{.spec.host}' -n $(NAMESPACE))/v1"; \
	MODEL_API_KEY=$$(oc get secret default-name-$$MODEL_NAME-sa -n $(NAMESPACE) -o jsonpath='{.data.token}' | base64 -d); \
	echo "Model name: $$MODEL_NAME"; \
	echo "Model endpoint: $$MODEL_URL"; \
	echo "Model API key: [extracted from service account token secret]"; \
	echo "Installing copilot-backend with auto-configured model settings..."; \
	helm -n $(NAMESPACE) upgrade --install copilot-backend $(COPILOT_BACKEND_CHART) \
		--set image.repository=image-registry.openshift-image-registry.svc:5000/$(NAMESPACE)/copilot-backend \
		--set image.tag=latest \
		--set image.pullPolicy=Always \
		--set llm.baseUrl=$$MODEL_URL \
		--set llm.model=$$MODEL_NAME \
		--set llm.apiKey=$$MODEL_API_KEY \
		$(if $(copilot.maxContextLength),--set llm.maxContextLength=$(copilot.maxContextLength),) \
		--timeout 5m
else
	@echo "Installing copilot-backend with configured model endpoint..."
	@helm -n $(NAMESPACE) upgrade --install copilot-backend $(COPILOT_BACKEND_CHART) \
		--set image.repository=image-registry.openshift-image-registry.svc:5000/$(NAMESPACE)/copilot-backend \
		--set image.tag=latest \
		--set image.pullPolicy=Always \
		$(if $(copilot.llmBaseUrl),--set llm.baseUrl=$(copilot.llmBaseUrl),) \
		$(if $(copilot.llmModel),--set llm.model=$(copilot.llmModel),) \
		$(if $(copilot.llmApiKey),--set llm.apiKey=$(copilot.llmApiKey),) \
		$(if $(copilot.maxContextLength),--set llm.maxContextLength=$(copilot.maxContextLength),) \
		--timeout 5m
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

# Build copilot-ui custom image
.PHONY: build-copilot-ui-image
build-copilot-ui-image:
	@echo "Creating ImageStream for copilot-ui..."
	@oc apply -f $(COPILOT_UI_CHART)/imagestream.yaml -n $(NAMESPACE)
	@echo "Getting copilot-backend route URL..."
	@BACKEND_URL=$$(oc get route copilot-backend -o jsonpath='https://{.spec.host}' -n $(NAMESPACE) 2>/dev/null || echo "http://copilot-backend:8080"); \
	echo "Backend URL: $$BACKEND_URL"; \
	echo "Creating BuildConfig for copilot-ui..."; \
	cat $(COPILOT_UI_CHART)/buildconfig.yaml | sed "s|\$${BACKEND_URL}|$$BACKEND_URL|g" | oc apply -f - -n $(NAMESPACE); \
	echo "Starting image build (this may take 3-5 minutes)..."; \
	echo "Uploading UI source files to OpenShift..."; \
	oc start-build copilot-ui --from-dir=../. --follow -n $(NAMESPACE) || echo "Build already running or completed"; \
	echo "copilot-ui image built successfully"

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

