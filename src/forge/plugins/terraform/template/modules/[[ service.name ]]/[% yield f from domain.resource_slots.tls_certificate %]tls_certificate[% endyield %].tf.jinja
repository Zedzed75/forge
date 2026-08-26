# =============================================================================
# tls_certificate.tf — certificat auto-signé des environnements de travail
# =============================================================================
# Fichier généré par forge.
#
# POUR LES ENVIRONNEMENTS DE TRAVAIL UNIQUEMENT. En production, un certificat
# auto-signé est refusé par tout client sérieux : employez cert-manager, ou un
# certificat émis par une autorité reconnue.
#
# ATTENTION — ce certificat expire sans rien signaler. Terraform ne le
# réengendre qu'au prochain « apply », et seulement si early_renewal_hours est
# atteint. Un projet appliqué deux fois par an avec un certificat d'un an tombe
# en panne un jour où personne n'a rien changé.
#
# ATTENTION — la clé privée est stockée en clair dans l'état Terraform, comme
# toute ressource du provider tls.
# =============================================================================

resource "tls_private_key" "this" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "tls_self_signed_cert" "this" {
  private_key_pem = tls_private_key.this.private_key_pem

  subject {
    common_name  = local.tls_common_name
    organization = var.service_name
  }

  # Ce sont ces noms que les navigateurs vérifient ; le Common Name est ignoré
  # depuis 2017. Une liste vide produit un certificat que rien n'acceptera.
  dns_names = var.tls_dns_names

  validity_period_hours = var.tls_validity_hours
  early_renewal_hours   = var.tls_early_renewal_hours

  allowed_uses = [
    "digital_signature",
    "key_encipherment",
    "server_auth",
  ]
}

resource "kubernetes_secret" "tls" {
  metadata {
    name        = "${var.service_name}-tls"
    namespace   = local.namespace
    labels      = local.labels
    annotations = var.annotations
  }

  # Ce type exige exactement les deux clés tls.crt et tls.key. Toute autre
  # nomenclature est acceptée par l'API et ignorée par l'ingress controller,
  # qui servira alors son certificat par défaut sans le dire.
  type = "kubernetes.io/tls"

  data = {
    "tls.crt" = tls_self_signed_cert.this.cert_pem
    "tls.key" = tls_private_key.this.private_key_pem
  }
}
