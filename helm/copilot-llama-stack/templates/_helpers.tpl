{{/*
Expand the name of the chart.
*/}}
{{- define "copilot-llama-stack.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "copilot-llama-stack.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "copilot-llama-stack.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "copilot-llama-stack.labels" -}}
helm.sh/chart: {{ include "copilot-llama-stack.chart" . }}
{{ include "copilot-llama-stack.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "copilot-llama-stack.selectorLabels" -}}
app.kubernetes.io/name: {{ include "copilot-llama-stack.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
MCP endpoint URI
*/}}
{{- define "copilot-llama-stack.mcpEndpoint" -}}
{{- printf "http://%s.%s.svc.cluster.local:%d/sse" .Values.mcp.serviceName .Release.Namespace (.Values.mcp.port | int) }}
{{- end }}

{{/*
vLLM service URL
*/}}
{{- define "copilot-llama-stack.vllmUrl" -}}
{{- if .Values.model.url }}
{{- .Values.model.url }}
{{- else }}
{{- printf "https://%s-predictor.%s.svc.cluster.local:8443/v1" .Values.model.name .Release.Namespace }}
{{- end }}
{{- end }}

{{/*
Storage backend database paths
*/}}
{{- define "copilot-llama-stack.kvDbPath" -}}
{{- printf "%s/%s" .Values.config.storage.basePath .Values.config.storage.kvBackend.dbName }}
{{- end }}

{{- define "copilot-llama-stack.sqlDbPath" -}}
{{- printf "%s/%s" .Values.config.storage.basePath .Values.config.storage.sqlBackend.dbName }}
{{- end }}
