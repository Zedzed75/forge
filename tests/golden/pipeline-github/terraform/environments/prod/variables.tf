# =============================================================================
# variables.tf — entrées de la racine « prod »
# =============================================================================
# Fichier généré par forge.
#
# Ces variables reprennent celles du module, plus ce qui concerne l'accès au
# cluster. Les valeurs de cet environnement sont dans terraform.tfvars ; toute
# variable non secrète peut y être surchargée, même celles que forge n'y a pas
# pré-remplies.
#
# Les variables secrètes n'ont pas de valeur par défaut et ne figurent pas dans
# terraform.tfvars : elles se fournissent par TF_VAR_<nom>.
# =============================================================================

# Chemin du fichier kubeconfig employe pour joindre le cluster. Propre a la
# machine : laissez la valeur par defaut et surchargez-la par
# TF_VAR_kube_config_path si besoin.
variable "kube_config_path" {
  description = "Chemin du fichier kubeconfig employe pour joindre le cluster. Propre a la machine : laissez la valeur par defaut et surchargez-la par TF_VAR_kube_config_path si besoin."
  type        = string
  default     = "~/.kube/config"
}

# Contexte kubeconfig vise. Ne le laissez jamais vide : sans contexte
# explicite, Terraform applique sur le contexte courant de la machine, quel
# qu'il soit.
variable "kube_context" {
  description = "Contexte kubeconfig vise. Ne le laissez jamais vide : sans contexte explicite, Terraform applique sur le contexte courant de la machine, quel qu'il soit."
  type        = string
  default     = ""
}

# Nom du service. Prefixe toutes les ressources creees et alimente le label
# app.kubernetes.io/name.
variable "service_name" {
  description = "Nom du service. Prefixe toutes les ressources creees et alimente le label app.kubernetes.io/name."
  type        = string
}

# Nom de l'environnement (dev, staging, prod). Sert de suffixe de ressource
# et de valeur du label app.kubernetes.io/instance.
variable "environment" {
  description = "Nom de l'environnement (dev, staging, prod). Sert de suffixe de ressource et de valeur du label app.kubernetes.io/instance."
  type        = string
}

# Namespace Kubernetes vise. Cree par ce module si la famille 'namespace'
# est retenue, suppose exister sinon.
variable "namespace" {
  description = "Namespace Kubernetes vise. Cree par ce module si la famille 'namespace' est retenue, suppose exister sinon."
  type        = string
}

# Labels apposes sur toutes les ressources, en plus des labels
# app.kubernetes.io calcules par le module.
variable "labels" {
  description = "Labels apposes sur toutes les ressources, en plus des labels app.kubernetes.io calcules par le module."
  type        = map(string)
  default     = {}
}

# Annotations apposees sur toutes les ressources. Laissez vide si aucun
# controleur du cluster n'en attend.
variable "annotations" {
  description = "Annotations apposees sur toutes les ressources. Laissez vide si aucun controleur du cluster n'en attend."
  type        = map(string)
  default     = {}
}

# Plafond de CPU demandable dans le namespace, en unites Kubernetes (ex. '4'
# pour 4 coeurs, '500m' pour un demi).
variable "quota_cpu" {
  description = "Plafond de CPU demandable dans le namespace, en unites Kubernetes (ex. '4' pour 4 coeurs, '500m' pour un demi)."
  type        = string
  default     = "4"
}

# Plafond de memoire demandable, suffixe Kubernetes obligatoire (Mi, Gi). Un
# nombre nu serait compris en octets.
variable "quota_memory" {
  description = "Plafond de memoire demandable, suffixe Kubernetes obligatoire (Mi, Gi). Un nombre nu serait compris en octets."
  type        = string
  default     = "8Gi"
}

# Nombre maximal de pods simultanes dans le namespace.
variable "quota_pods" {
  description = "Nombre maximal de pods simultanes dans le namespace."
  type        = number
  default     = 30
}

# CPU attribue a un conteneur qui n'en demande pas.
variable "limit_range_default_cpu" {
  description = "CPU attribue a un conteneur qui n'en demande pas."
  type        = string
  default     = "500m"
}

# Memoire attribuee a un conteneur qui n'en demande pas.
variable "limit_range_default_memory" {
  description = "Memoire attribuee a un conteneur qui n'en demande pas."
  type        = string
  default     = "512Mi"
}
