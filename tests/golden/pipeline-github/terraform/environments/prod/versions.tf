# =============================================================================
# versions.tf — versions exigées par la racine « prod »
# =============================================================================
# Fichier généré par forge.
#
# Chaque racine redéclare ses providers : Terraform ne les hérite pas du
# module appelé. Les contraintes sont volontairement identiques à celles du
# module — deux déclarations divergentes ne produisent aucune erreur, Terraform
# résout l'intersection, et l'écart ne se voit que le jour où elle devient vide.
# =============================================================================

terraform {
  required_version = "~> 1.9"

  required_providers {
    # pose les objets Kubernetes qui accueillent le service
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.32"
    }
  }
}
