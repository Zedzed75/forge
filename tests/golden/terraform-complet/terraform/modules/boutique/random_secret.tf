# =============================================================================
# random_secret.tf — mots de passe engendrés, déposés en Secret
# =============================================================================
# Fichier généré par forge.
#
# Aucune valeur secrète n'entre dans forge.yml ni dans un fichier généré : ces
# valeurs n'existent qu'une fois appliquées. C'est tout l'intérêt de la famille.
#
# ATTENTION — random_password conserve la valeur EN CLAIR dans l'état
# Terraform. Le mot de passe n'est pas plus secret que l'état : un backend
# chiffré et à l'accès restreint est une condition, pas une amélioration.
#
# ATTENTION — le service qui lit ce Secret ne le relit pas seul. Monté en
# volume, il est rafraîchi avec du retard ; injecté en variable
# d'environnement, il ne l'est JAMAIS avant un redémarrage du pod.
# =============================================================================

resource "random_password" "generated" {
  for_each = toset(var.generated_secret_keys)

  length = var.generated_secret_length

  # Caractères spéciaux restreints : @ / : ? # brisent les URL de connexion du
  # type postgres://utilisateur:motdepasse@hote/base, et le diagnostic est
  # long parce que la panne ressemble à une erreur d'authentification.
  special          = true
  override_special = "-_=+."

  # Sans keepers, la valeur ne change jamais — comportement voulu, mais qui
  # interdit toute rotation. Faire tourner un mot de passe consiste à modifier
  # un keeper, jamais à détruire la ressource.
  keepers = {
    environment = var.environment
  }
}

resource "kubernetes_secret" "generated" {
  metadata {
    name        = "${var.service_name}-generated"
    namespace   = local.namespace
    labels      = local.labels
    annotations = var.annotations
  }

  type = "Opaque"

  data = { for cle, motdepasse in random_password.generated : cle => motdepasse.result }
}
