# =============================================================================
# locals.tf — valeurs calculées une fois pour tout le module
# =============================================================================
# Fichier généré par forge.
# =============================================================================

locals {
  # Le namespace est lu sur la ressource plutôt que sur la variable, et c'est
  # volontaire : cette référence donne à Terraform l'ordre de création. Tout ce
  # qui emploie local.namespace attend donc la création du namespace, sans
  # qu'aucun depends_on n'ait à l'écrire.
  namespace = kubernetes_namespace.this.metadata[0].name

  # Labels apposés sur chaque ressource. Les quatre premiers sont les labels
  # recommandés par Kubernetes ; les charts Helm du même service posent les
  # mêmes, ce qui permet de retrouver d'un seul « kubectl get -l » tout ce qui
  # appartient au service, quel que soit l'outil qui l'a posé.
  labels = merge({
    "app.kubernetes.io/name"       = var.service_name
    "app.kubernetes.io/instance"   = "${var.service_name}-${var.environment}"
    "app.kubernetes.io/part-of"    = var.service_name
    "app.kubernetes.io/managed-by" = "terraform"
  }, var.labels)

  # Nom du ServiceAccount de déploiement. Laissé vide dans les variables, il se
  # déduit du nom du service : un nom par défaut prévisible vaut mieux qu'une
  # valeur à renseigner dans chaque environnement.
  service_account_name = var.service_account_name != "" ? var.service_account_name : "${var.service_name}-deployer"

  # Common Name du certificat. Les navigateurs l'ignorent depuis 2017 — c'est
  # la liste dns_names qui fait foi — mais un certificat sans CN est refusé par
  # certaines bibliothèques anciennes.
  tls_common_name = var.tls_common_name != "" ? var.tls_common_name : (length(var.tls_dns_names) > 0 ? var.tls_dns_names[0] : var.service_name)
}
