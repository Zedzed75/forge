# =============================================================================
# outputs.tf — sorties de l'environnement « prod »
# =============================================================================
# Fichier généré par forge.
#
# Ces sorties sont le point de rencontre avec le reste de la chaîne : c'est par
#
#   terraform -chdir=environments/prod output -raw namespace
#
# qu'un pipeline apprend où déployer, plutôt que de recopier une convention de
# nommage qui finirait par diverger.
# =============================================================================

# Namespace dans lequel le service est deploye.
output "namespace" {
  description = "Namespace dans lequel le service est deploye."
  value       = module.boutique.namespace
}

# Nom du ResourceQuota pose sur le namespace.
output "resource_quota_name" {
  description = "Nom du ResourceQuota pose sur le namespace."
  value       = module.boutique.resource_quota_name
}

# Nom du Secret a citer dans imagePullSecrets, cote chart Helm.
output "image_pull_secret_name" {
  description = "Nom du Secret a citer dans imagePullSecrets, cote chart Helm."
  value       = module.boutique.image_pull_secret_name
}

# Nom du ServiceAccount de deploiement.
output "service_account_name" {
  description = "Nom du ServiceAccount de deploiement."
  value       = module.boutique.service_account_name
}

# Nom du Secret portant les valeurs engendrees. Sa valeur n'est pas exposee
# en sortie.
output "generated_secret_name" {
  description = "Nom du Secret portant les valeurs engendrees. Sa valeur n'est pas exposee en sortie."
  value       = module.boutique.generated_secret_name
}

# Nom du Secret kubernetes.io/tls a citer dans l'Ingress.
output "tls_secret_name" {
  description = "Nom du Secret kubernetes.io/tls a citer dans l'Ingress."
  value       = module.boutique.tls_secret_name
}
