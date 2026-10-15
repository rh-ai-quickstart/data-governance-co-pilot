{{/*
Parent-chart helpers matching aws-compatible-storage.fullnameOverride. These
are used by the parent-owned bucket bootstrap Job.
*/}}
{{- define "aws-compatible-storage.fullname" -}}
{{- $storage := index .Values "aws-compatible-storage" | default dict -}}
{{- $storage.fullnameOverride | default "aws-compatible-storage" -}}
{{- end -}}

{{- define "aws-compatible-storage.secretName" -}}
{{- printf "%s-credentials" (include "aws-compatible-storage.fullname" .) -}}
{{- end -}}

{{- define "aws-compatible-storage.apiPort" -}}
7480
{{- end -}}

{{- define "aws-compatible-storage.uiPort" -}}
5000
{{- end -}}
