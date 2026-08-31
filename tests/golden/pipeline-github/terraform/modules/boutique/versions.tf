# =============================================================================
# versions.tf — versions exigées par le module « boutique »
# =============================================================================
# Fichier généré par forge.
#
# Un module déclare les versions dont il a besoin ; il ne configure jamais un
# provider. C'est la racine appelante — environments/<env>/providers.tf — qui
# décide quel cluster est visé. Un bloc « provider » écrit ici rendrait le
# module inutilisable ailleurs.
# =============================================================================

terraform {
  # Borne haute obligatoire : une contrainte ouverte laisserait une version
  # majeure future de Terraform casser ce module sans qu'on ait rien changé.
  required_version = "~> 1.9"

  required_providers {
    # pose les objets Kubernetes qui accueillent le service
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.32"
    }
  }
}
