{{/*
Namespace helper — defaults to "aic" if .Values.namespace is unset.
*/}}
{{- define "aic.namespace" -}}
{{- .Values.namespace | default "aic" -}}
{{- end }}

{{/*
Common chart labels applied to every resource.
*/}}
{{- define "aic.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}
