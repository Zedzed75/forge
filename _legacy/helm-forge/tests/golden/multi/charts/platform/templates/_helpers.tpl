{{/*
===============================================================================
_helpers.tpl — fonctions de nommage et d'étiquetage du chart « platform »
===============================================================================
Fichier généré par helm-forge.

Aucun nom de ressource ni aucun label n'est écrit en dur dans les gabarits :
tout passe par les helpers définis ici. Une seule modification suffit donc pour
renommer ou réétiqueter l'ensemble du chart.

Convention de nommage des helpers :
  platform.<nom>              helper global au chart
  platform.<composant>.<nom>  helper propre à un composant
===============================================================================
*/}}

{{/*
Nom du chart, éventuellement remplacé par nameOverride.
Tronqué à 63 caractères : c'est la limite d'un label DNS-1123, et un nom plus
long serait refusé par l'API Kubernetes.
*/}}
{{- define "platform.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Nom complet des ressources : <release>-<chart>.
Lorsque le nom de la release contient déjà le nom du chart, il est utilisé seul
afin d'éviter les doublons du type « shop-shop ».
*/}}
{{- define "platform.fullname" -}}
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
Identifiant du chart, au format <nom>-<version>, posé dans le label
helm.sh/chart. Le « + » d'un éventuel build SemVer est remplacé : il n'est pas
autorisé dans une valeur de label.
*/}}
{{- define "platform.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Labels de sélection : sous-ensemble stable et immuable des labels.
Ils servent de selector aux Deployments et aux Services ; ne jamais y ajouter
une valeur changeante comme la version, sous peine de rendre le Deployment non
modifiable (le champ selector est immuable après création).
*/}}
{{- define "platform.selectorLabels" -}}
app.kubernetes.io/name: {{ include "platform.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Labels standards recommandés par Kubernetes, posés sur toutes les ressources.
*/}}
{{- define "platform.labels" -}}
helm.sh/chart: {{ include "platform.chart" . }}
{{ include "platform.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- if .Values.global.environment }}
environment: {{ .Values.global.environment | quote }}
{{- end }}
{{- end }}

{{/*
-------------------------------------------------------------------------------
Composant « api »
-------------------------------------------------------------------------------
*/}}

{{/*
Nom complet des ressources du composant : <release>-<chart>-api.
*/}}
{{- define "platform.api.fullname" -}}
{{- printf "%s-%s" (include "platform.fullname" .) "api" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Labels de sélection du composant : ceux du chart, plus le label de composant.
*/}}
{{- define "platform.api.selectorLabels" -}}
{{ include "platform.selectorLabels" . }}
app.kubernetes.io/component: api
{{- end }}

{{/*
Labels complets du composant.
*/}}
{{- define "platform.api.labels" -}}
{{ include "platform.labels" . }}
app.kubernetes.io/component: api
{{- end }}

{{/*
Référence complète de l'image : <registry>/<dépôt>:<tag>.
Le tag laissé vide dans les values retombe sur appVersion du Chart.yaml, ce qui
évite d'avoir à le renseigner à deux endroits à chaque livraison.
*/}}
{{- define "platform.api.image" -}}
{{- $values := .Values.api -}}
{{- $tag := $values.image.tag | default .Chart.AppVersion -}}
{{- if .Values.global.imageRegistry -}}
{{- printf "%s/%s:%s" .Values.global.imageRegistry $values.image.repository $tag -}}
{{- else -}}
{{- printf "%s:%s" $values.image.repository $tag -}}
{{- end -}}
{{- end }}
{{/*
-------------------------------------------------------------------------------
Composant « worker »
-------------------------------------------------------------------------------
*/}}

{{/*
Nom complet des ressources du composant : <release>-<chart>-worker.
*/}}
{{- define "platform.worker.fullname" -}}
{{- printf "%s-%s" (include "platform.fullname" .) "worker" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Labels de sélection du composant : ceux du chart, plus le label de composant.
*/}}
{{- define "platform.worker.selectorLabels" -}}
{{ include "platform.selectorLabels" . }}
app.kubernetes.io/component: worker
{{- end }}

{{/*
Labels complets du composant.
*/}}
{{- define "platform.worker.labels" -}}
{{ include "platform.labels" . }}
app.kubernetes.io/component: worker
{{- end }}

{{/*
Référence complète de l'image : <registry>/<dépôt>:<tag>.
Le tag laissé vide dans les values retombe sur appVersion du Chart.yaml, ce qui
évite d'avoir à le renseigner à deux endroits à chaque livraison.
*/}}
{{- define "platform.worker.image" -}}
{{- $values := .Values.worker -}}
{{- $tag := $values.image.tag | default .Chart.AppVersion -}}
{{- if .Values.global.imageRegistry -}}
{{- printf "%s/%s:%s" .Values.global.imageRegistry $values.image.repository $tag -}}
{{- else -}}
{{- printf "%s:%s" $values.image.repository $tag -}}
{{- end -}}
{{- end }}
