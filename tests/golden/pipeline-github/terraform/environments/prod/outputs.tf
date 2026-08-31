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
