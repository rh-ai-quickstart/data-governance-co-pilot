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

MINIMUM_OC_VERSION = "4.17.0"
MINIMUM_USERID_LENGTH = 3
MINIMUM_PASSWORD_LENGTH = 8

# Default target
.PHONY: help
help:
	@echo "Available targets:"
	@echo "  install       - Installs quickstart and supporting resources"
	@echo "                  Required: NAMESPACE, postgres.userId, postgres.password, postgres.databaseName, minio.userId, minio.password"
	@echo "                  Example: make install NAMESPACE=myns postgres.userId=postgres postgres.password=pass123 postgres.databaseName=recsys minio.userId=minio minio.password=minio123"
	@echo "  uninstall     - Uninstalls the quickstart and clean up resources"
	@echo ""
	@echo "Configuration options (set via environment variables or make arguments):"
	@echo "  NAMESPACE                - Target namespace (required)"
	@echo "  postgres.userId          - PostgreSQL userId (required)"
	@echo "  postgres.password        - PostgreSQL password (required)"
	@echo "  postgres.databaseName    - PostgreSQL database name (required)"
	@echo "  minio.userId             - User ID to use for minio installation (required)"
	@echo "  minio.password           - Password to use for minio installation (required)"

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

.PHONY: namespace
namespace:
	@oc create namespace $(NAMESPACE) &> /dev/null && oc label namespace $(NAMESPACE) modelmesh-enabled=false ||:
	@oc project $(NAMESPACE) &> /dev/null ||:

.PHONY: install
install: check-oc-version check-minio-credentials check-postgres-credentials namespace minio-install database-install

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

.PHONY: uninstall
uninstall: check-oc-version minio-uninstall database-uninstall delete-project

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

.PHONY: delete-project
delete-project:
	@echo "Attempting to delete OpenShift project $(NAMESPACE)..."
	@oc delete project $(NAMESPACE)

