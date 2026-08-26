# =============================================================================
# quota.tf — budget du namespace : ResourceQuota et LimitRange
# =============================================================================
# Fichier généré par forge.
#
# CONSÉQUENCE À CONNAÎTRE — dès qu'un ResourceQuota porte sur requests.cpu ou
# requests.memory, l'API refuse tout pod dont un conteneur ne déclare pas ses
# « resources.requests ». Le chart Helm du même service doit donc les déclarer,
# sinon le déploiement casse le jour où ce quota est posé, et pas avant.
#
# Le LimitRange amortit ce risque en donnant une taille par défaut aux
# conteneurs qui n'en demandent pas — mais seulement aux pods créés APRÈS lui :
# les pods déjà en place gardent leur configuration jusqu'au redémarrage.
# =============================================================================

resource "kubernetes_resource_quota" "this" {
  metadata {
    name        = "${var.service_name}-quota"
    namespace   = local.namespace
    labels      = local.labels
    annotations = var.annotations
  }

  spec {
    # Les mêmes valeurs plafonnent les requests et les limits : un namespace
    # dont la somme des limits dépasse largement la somme des requests promet
    # plus de ressources qu'il n'en a, et l'éviction arrive sous charge.
    hard = {
      "requests.cpu"    = var.quota_cpu
      "requests.memory" = var.quota_memory
      "limits.cpu"      = var.quota_cpu
      "limits.memory"   = var.quota_memory
      "pods"            = var.quota_pods
    }
  }
}

resource "kubernetes_limit_range" "this" {
  metadata {
    name        = "${var.service_name}-limits"
    namespace   = local.namespace
    labels      = local.labels
    annotations = var.annotations
  }

  spec {
    limit {
      type = "Container"

      # « default » fixe la limite ; « default_request » fixe la demande. Ne
      # renseigner que le premier ferait recopier la limite dans la demande,
      # et réserverait bien plus de ressources que prévu.
      default = {
        cpu    = var.limit_range_default_cpu
        memory = var.limit_range_default_memory
      }

      default_request = {
        cpu    = var.limit_range_default_cpu
        memory = var.limit_range_default_memory
      }
    }
  }
}
