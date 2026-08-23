{{/*
===============================================================================
_helpers.tpl — fonctions de nommage et d'étiquetage du chart « shop »
===============================================================================
Fichier généré par helm-forge.

Aucun nom de ressource ni aucun label n'est écrit en dur dans les gabarits :
tout passe par les helpers définis ici. Une seule modification suffit donc pour
renommer ou réétiqueter l'ensemble du chart.

Convention de nommage des helpers :
  shop.<nom>              helper global au chart
  shop.<composant>.<nom>  helper propre à un composant
===============================================================================
*/}}

{{/*
Nom du chart, éventuellement remplacé par nameOverride.
Tronqué à 63 caractères : c'est la limite d'un label DNS-1123, et un nom plus
long serait refusé par l'API Kubernetes.
*/}}
{{- define "shop.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Nom complet des ressources : <release>-<chart>.
Lorsque le nom de la release contient déjà le nom du chart, il est utilisé seul
afin d'éviter les doublons du type « shop-shop ».
*/}}
{{- define "shop.fullname" -}}
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
{{- define "shop.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Labels de sélection : sous-ensemble stable et immuable des labels.
Ils servent de selector aux Deployments et aux Services ; ne jamais y ajouter
une valeur changeante comme la version, sous peine de rendre le Deployment non
modifiable (le champ selector est immuable après création).
*/}}
{{- define "shop.selectorLabels" -}}
app.kubernetes.io/name: {{ include "shop.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Labels standards recommandés par Kubernetes, posés sur toutes les ressources.
*/}}
{{- define "shop.labels" -}}
helm.sh/chart: {{ include "shop.chart" . }}
{{ include "shop.selectorLabels" . }}
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
{{- define "shop.api.fullname" -}}
{{- printf "%s-%s" (include "shop.fullname" .) "api" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Labels de sélection du composant : ceux du chart, plus le label de composant.
*/}}
{{- define "shop.api.selectorLabels" -}}
{{ include "shop.selectorLabels" . }}
app.kubernetes.io/component: api
{{- end }}

{{/*
Labels complets du composant.
*/}}
{{- define "shop.api.labels" -}}
{{ include "shop.labels" . }}
app.kubernetes.io/component: api
{{- end }}

{{/*
Référence complète de l'image : <registry>/<dépôt>:<tag>.
Le tag laissé vide dans les values retombe sur appVersion du Chart.yaml, ce qui
évite d'avoir à le renseigner à deux endroits à chaque livraison.
*/}}
{{- define "shop.api.image" -}}
{{- $values := .Values.api -}}
{{- $tag := $values.image.tag | default .Chart.AppVersion -}}
{{- if .Values.global.imageRegistry -}}
{{- printf "%s/%s:%s" .Values.global.imageRegistry $values.image.repository $tag -}}
{{- else -}}
{{- printf "%s:%s" $values.image.repository $tag -}}
{{- end -}}
{{- end }}
