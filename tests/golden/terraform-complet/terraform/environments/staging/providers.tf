# =============================================================================
# providers.tf — comment cette racine joint le cluster
# =============================================================================
# Fichier généré par forge.
#
# C'est le seul endroit du projet qui sait vers quel cluster part un « apply ».
# Le module, lui, ne le sait pas : c'est ce qui le rend réutilisable.
#
# ATTENTION — sans « config_context », le provider emploie le contexte COURANT
# du kubeconfig de la machine. Appliquer en production depuis un poste mal
# positionné est l'accident le plus banal de ce provider ; la variable
# kube_context existe pour l'empêcher, ne la laissez pas vide.
# =============================================================================

provider "kubernetes" {
  config_path    = var.kube_config_path
  config_context = var.kube_context
}

# Le provider « random » ne demande aucune configuration : il
# n'appelle aucun service distant. Le bloc est déclaré pour que la
# configuration soit lisible d'un seul fichier.
provider "random" {
}

# Le provider « tls » ne demande aucune configuration : il
# n'appelle aucun service distant. Le bloc est déclaré pour que la
# configuration soit lisible d'un seul fichier.
provider "tls" {
}
