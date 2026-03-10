#!/bin/zsh

podman image prune --all --force

cd ./apps/ui/
podman build --platform linux/amd64 -t quay.io/rh-ai-quickstart/copilot-ui:latest -f Containerfile .
podman push quay.io/rh-ai-quickstart/copilot-ui:latest

