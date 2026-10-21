#!/bin/zsh
set -e

podman image prune --all --force

cd ./apps/ui/
podman build --platform linux/amd64 -t quay.io/rh-ai-quickstart/copilot-ui:latest -f Containerfile .
podman push quay.io/rh-ai-quickstart/copilot-ui:latest

# pg-airman-mcp is not rebuilt: the quickstart is pinned to the existing v1.0.0 image
# (quay.io/rh-ai-quickstart/pg-airman-mcp:1.0.0), which can no longer be built from source.

cd ../../
podman build --platform linux/amd64 -t quay.io/rh-ai-quickstart/copilot-backend:latest -f helm/copilot-backend/Containerfile .
podman push quay.io/rh-ai-quickstart/copilot-backend:latest

cd helm/pgvector/
podman build --platform linux/amd64 -t quay.io/rh-ai-quickstart/pgvector-data-loader:latest -f Containerfile .
podman push quay.io/rh-ai-quickstart/pgvector-data-loader:latest
