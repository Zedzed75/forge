# =============================================================================
# registry_secret.tf — secret de tirage d'image pour un registre privé
# =============================================================================
# Fichier généré par forge.
#
# Aucun identifiant n'est écrit ici ni dans terraform.tfvars : le mot de passe
# arrive par la variable d'environnement TF_VAR_registry_password.
#
# ATTENTION — le champ « auth » du document est un encodage base64 du couple
# utilisateur:motdepasse, pas un chiffrement. Quiconque lit l'état Terraform ou
# le Secret Kubernetes lit le mot de passe. Un compte de service en lecture
# seule, propre au cluster, est la seule réponse raisonnable.
#
# ATTENTION — un imagePullSecret ne vaut que dans son namespace. Un service
# déployé dans plusieurs namespaces a besoin d'un Secret par namespace.
# =============================================================================

resource "kubernetes_secret" "registry" {
  metadata {
    name        = "${var.service_name}-registry"
    namespace   = local.namespace
    labels      = local.labels
    annotations = var.annotations
  }

  # Ce type impose la clé « .dockerconfigjson », point initial compris. Une
  # clé « auths » nue est acceptée par l'API et rejetée par kubelet au premier
  # tirage, avec une erreur ImagePullBackOff qui ne dit pas pourquoi.
  type = "kubernetes.io/dockerconfigjson"

  # « data » reçoit du texte clair : le provider l'encode lui-même en base64.
  # Y passer une valeur déjà encodée la double-encoderait en silence.
  data = {
    ".dockerconfigjson" = jsonencode({
      auths = {
        (var.registry_server) = {
          username = var.registry_username
          password = var.registry_password
          auth     = base64encode("${var.registry_username}:${var.registry_password}")
        }
      }
    })
  }
}
