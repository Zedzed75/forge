# =============================================================================
# network_policy.tf — le namespace est fermé, puis rouvert au strict nécessaire
# =============================================================================
# Fichier généré par forge.
#
# ATTENTION — sans plugin réseau qui les applique (Calico, Cilium, Antrea), une
# NetworkPolicy est acceptée par l'API et reste SANS AUCUN EFFET. Le namespace
# paraît protégé et ne l'est pas. Vérifiez le CNI du cluster avant de vous fier
# à ce fichier.
#
# ATTENTION — une politique deny-by-default sans ouverture vers le DNS casse
# toute résolution de nom dans le namespace. La panne se présente comme une
# lenteur applicative, jamais comme un problème réseau : d'où la première règle
# d'egress ci-dessous, qui n'est pas facultative.
# =============================================================================

resource "kubernetes_network_policy" "default_deny" {
  metadata {
    name        = "${var.service_name}-default-deny"
    namespace   = local.namespace
    labels      = local.labels
    annotations = var.annotations
  }

  spec {
    # Un pod_selector vide sélectionne TOUS les pods du namespace. C'est
    # exactement ce qu'on veut ici, et exactement ce qu'il ne faut pas écrire
    # dans une règle d'ouverture.
    pod_selector {
    }

    policy_types = ["Ingress", "Egress"]

    # Résolution DNS. Les deux protocoles sont nécessaires : UDP pour les
    # requêtes courantes, TCP pour les réponses trop grandes pour un datagramme.
    egress {
      ports {
        port     = "53"
        protocol = "UDP"
      }

      ports {
        port     = "53"
        protocol = "TCP"
      }

      to {
        namespace_selector {
          match_labels = var.dns_namespace_labels
        }
      }
    }

    # Trafic sortant vers les autres pods du même namespace.
    egress {
      to {
        pod_selector {
        }
      }
    }

    # Trafic entrant venant des autres pods du même namespace.
    ingress {
      from {
        pod_selector {
        }
      }
    }
  }
}

resource "kubernetes_network_policy" "allow_ingress_controller" {
  # Pas de règle d'ouverture si aucun namespace d'ingress n'est désigné : le
  # service reste alors joignable depuis son seul namespace.
  count = length(var.ingress_namespace_labels) > 0 ? 1 : 0

  metadata {
    name        = "${var.service_name}-allow-ingress"
    namespace   = local.namespace
    labels      = local.labels
    annotations = var.annotations
  }

  spec {
    pod_selector {
      match_labels = {
        "app.kubernetes.io/name" = var.service_name
      }
    }

    policy_types = ["Ingress"]

    # namespace_selector seul, dans son propre bloc « from » : ajouter un
    # pod_selector dans le MÊME bloc formerait un ET, dans un bloc séparé un
    # OU. L'écart entre les deux est une ouverture bien plus large que prévu,
    # et rien ne le signale.
    ingress {
      from {
        namespace_selector {
          match_labels = var.ingress_namespace_labels
        }
      }
    }
  }
}
