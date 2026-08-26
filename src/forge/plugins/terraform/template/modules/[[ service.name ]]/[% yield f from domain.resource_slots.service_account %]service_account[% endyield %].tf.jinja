# =============================================================================
# service_account.tf — identité de déploiement du service
# =============================================================================
# Fichier généré par forge.
#
# Donne à la chaîne de déploiement une identité propre au namespace, avec les
# droits d'un « helm upgrade » et rien de plus. Aucun droit cluster-scoped :
# un Role ne porte que dans son namespace, et c'est voulu.
#
# ATTENTION — depuis Kubernetes 1.24, aucun Secret de jeton n'est créé
# automatiquement pour un ServiceAccount. Pour obtenir un jeton, préférez
# « kubectl create token » (jeton court, révocable) à un Secret durable de type
# kubernetes.io/service-account-token.
# =============================================================================

resource "kubernetes_service_account" "deployer" {
  metadata {
    name        = local.service_account_name
    namespace   = local.namespace
    labels      = local.labels
    annotations = var.annotations
  }
}

resource "kubernetes_role" "deployer" {
  metadata {
    name        = local.service_account_name
    namespace   = local.namespace
    labels      = local.labels
    annotations = var.annotations
  }

  # Objets du groupe d'API « core » (api_groups = [""]).
  rule {
    api_groups = [""]
    resources  = ["configmaps", "persistentvolumeclaims", "pods", "secrets", "serviceaccounts", "services"]
    verbs      = ["get", "list", "watch", "create", "update", "patch", "delete"]
  }

  # Charges de travail.
  rule {
    api_groups = ["apps"]
    resources  = ["daemonsets", "deployments", "replicasets", "statefulsets"]
    verbs      = ["get", "list", "watch", "create", "update", "patch", "delete"]
  }

  # Tâches planifiées.
  rule {
    api_groups = ["batch"]
    resources  = ["cronjobs", "jobs"]
    verbs      = ["get", "list", "watch", "create", "update", "patch", "delete"]
  }

  # Exposition réseau.
  rule {
    api_groups = ["networking.k8s.io"]
    resources  = ["ingresses", "networkpolicies"]
    verbs      = ["get", "list", "watch", "create", "update", "patch", "delete"]
  }

  # Mise à l'échelle et disponibilité.
  rule {
    api_groups = ["autoscaling", "policy"]
    resources  = ["horizontalpodautoscalers", "poddisruptionbudgets"]
    verbs      = ["get", "list", "watch", "create", "update", "patch", "delete"]
  }
}

resource "kubernetes_role_binding" "deployer" {
  metadata {
    name        = local.service_account_name
    namespace   = local.namespace
    labels      = local.labels
    annotations = var.annotations
  }

  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "Role"
    name      = kubernetes_role.deployer.metadata[0].name
  }

  # Le groupe d'API d'un sujet ServiceAccount est la chaîne vide. C'est
  # rbac.authorization.k8s.io qui vaut pour un User ou un Group : l'inverse est
  # accepté par Terraform et rejeté par l'API au moment d'appliquer.
  subject {
    api_group = ""
    kind      = "ServiceAccount"
    name      = kubernetes_service_account.deployer.metadata[0].name
    namespace = local.namespace
  }
}
