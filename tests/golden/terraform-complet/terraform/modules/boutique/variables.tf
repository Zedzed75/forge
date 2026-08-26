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

# Adresse du registre. Docker Hub exige la forme historique
# https://index.docker.io/v1/ ; les autres registres prennent leur nom
# d'hote nu.
variable "registry_server" {
  description = "Adresse du registre. Docker Hub exige la forme historique https://index.docker.io/v1/ ; les autres registres prennent leur nom d'hote nu."
  type        = string
  default     = "https://index.docker.io/v1/"
}

# Identifiant de lecture sur le registre. Employez un compte de service en
# lecture seule, jamais un compte nominatif.
variable "registry_username" {
  description = "Identifiant de lecture sur le registre. Employez un compte de service en lecture seule, jamais un compte nominatif."
  type        = string
  default     = ""
}

# Mot de passe ou jeton du registre. Sans valeur par defaut et absent de
# terraform.tfvars : fournissez-le par TF_VAR_registry_password.
# Valeur secrète : aucune valeur par défaut, et absente de terraform.tfvars.
# Fournissez-la par la variable d'environnement TF_VAR_registry_password.
variable "registry_password" {
  description = "Mot de passe ou jeton du registre. Sans valeur par defaut et absent de terraform.tfvars : fournissez-le par TF_VAR_registry_password."
  type        = string
  sensitive   = true
}

# Nom du ServiceAccount. Vide, il vaut '<service>-deployer'.
variable "service_account_name" {
  description = "Nom du ServiceAccount. Vide, il vaut '<service>-deployer'."
  type        = string
  default     = ""
}

# Labels du namespace autorise a joindre le service (celui de l'ingress
# controller). Vide, seul le trafic interne au namespace est autorise.
variable "ingress_namespace_labels" {
  description = "Labels du namespace autorise a joindre le service (celui de l'ingress controller). Vide, seul le trafic interne au namespace est autorise."
  type        = map(string)
  default     = { "kubernetes.io/metadata.name" = "ingress-nginx" }
}

# Labels du namespace hebergeant le service DNS du cluster. Sans cette
# ouverture, plus aucun nom ne se resout.
variable "dns_namespace_labels" {
  description = "Labels du namespace hebergeant le service DNS du cluster. Sans cette ouverture, plus aucun nom ne se resout."
  type        = map(string)
  default     = { "kubernetes.io/metadata.name" = "kube-system" }
}

# Cles a engendrer dans le Secret (ex. ['database-password', 'api-token']).
# Une valeur aleatoire est produite par cle.
variable "generated_secret_keys" {
  description = "Cles a engendrer dans le Secret (ex. ['database-password', 'api-token']). Une valeur aleatoire est produite par cle."
  type        = list(string)
  default     = ["password"]
}

# Longueur de chaque valeur engendree, en caracteres.
variable "generated_secret_length" {
  description = "Longueur de chaque valeur engendree, en caracteres."
  type        = number
  default     = 32
}

# Nom porte par le certificat (CN). Vide, il vaut le premier nom de
# tls_dns_names.
variable "tls_common_name" {
  description = "Nom porte par le certificat (CN). Vide, il vaut le premier nom de tls_dns_names."
  type        = string
  default     = ""
}

# Noms DNS couverts par le certificat (SAN). Les navigateurs ignorent le CN
# depuis longtemps : c'est cette liste qui compte.
variable "tls_dns_names" {
  description = "Noms DNS couverts par le certificat (SAN). Les navigateurs ignorent le CN depuis longtemps : c'est cette liste qui compte."
  type        = list(string)
  default     = []
}

# Duree de validite du certificat, en heures (8760 = un an).
variable "tls_validity_hours" {
  description = "Duree de validite du certificat, en heures (8760 = un an)."
  type        = number
  default     = 8760
}

# Delai avant expiration a partir duquel un apply reengendre le certificat,
# en heures (720 = trente jours).
variable "tls_early_renewal_hours" {
  description = "Delai avant expiration a partir duquel un apply reengendre le certificat, en heures (720 = trente jours)."
  type        = number
  default     = 720
}
