# =============================================================================
# variables.tf — entrées du module « boutique »
# =============================================================================
# Fichier généré par forge.
#
# Chaque variable porte deux fois son explication, et ce n'est pas une
# redondance : le commentaire s'adresse à qui lit le fichier, l'attribut
# « description » à qui lit « terraform plan », la documentation générée par
# terraform-docs, ou le message d'erreur d'une variable manquante.
#
# Les variables sans valeur par défaut sont obligatoires : Terraform les
# réclame, et « -input=false » transforme l'oubli en échec net plutôt qu'en
# question restée sans réponse dans un journal de CI.
# =============================================================================

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
