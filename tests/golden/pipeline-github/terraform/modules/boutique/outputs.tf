# =============================================================================
# outputs.tf — ce que le module rend à son appelant
# =============================================================================
# Fichier généré par forge.
#
# Les sorties sont le contrat du module vers le reste de la chaîne : c'est par
# « terraform output -raw namespace » qu'un pipeline apprend où déployer, sans
# recopier une convention de nommage qui pourrait dériver.
#
# Aucune sortie ne rend une valeur secrète. Un mot de passe engendré reste dans
# l'état ; le module ne fait que nommer le Secret qui le porte.
# =============================================================================

# Namespace dans lequel le service est deploye.
output "namespace" {
  description = "Namespace dans lequel le service est deploye."
  value       = local.namespace
}

# Nom du ResourceQuota pose sur le namespace.
output "resource_quota_name" {
  description = "Nom du ResourceQuota pose sur le namespace."
  value       = kubernetes_resource_quota.this.metadata[0].name
}
