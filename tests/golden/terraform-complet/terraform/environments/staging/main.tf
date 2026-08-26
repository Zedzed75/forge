# =============================================================================
# main.tf — appel du module pour l'environnement « staging »
# =============================================================================
# Fichier généré par forge.
#
# Le module est écrit une seule fois et appelé une fois par environnement :
# c'est ce qui garantit que dev et prod posent les mêmes objets, aux valeurs
# près. Les valeurs, elles, sont dans terraform.tfvars.
#
# Chaque argument est transmis explicitement. Terraform signale bruyamment un
# argument que le module ne déclare pas ; il ne dit RIEN d'une variable
# déclarée et jamais transmise — elle prend simplement sa valeur par défaut, et
# l'écart ne se voit jamais.
# =============================================================================

module "boutique" {
  source = "../../modules/boutique"

  service_name               = var.service_name
  environment                = var.environment
  namespace                  = var.namespace
  labels                     = var.labels
  annotations                = var.annotations
  quota_cpu                  = var.quota_cpu
  quota_memory               = var.quota_memory
  quota_pods                 = var.quota_pods
  limit_range_default_cpu    = var.limit_range_default_cpu
  limit_range_default_memory = var.limit_range_default_memory
  registry_server            = var.registry_server
  registry_username          = var.registry_username
  registry_password          = var.registry_password
  service_account_name       = var.service_account_name
  ingress_namespace_labels   = var.ingress_namespace_labels
  dns_namespace_labels       = var.dns_namespace_labels
  generated_secret_keys      = var.generated_secret_keys
  generated_secret_length    = var.generated_secret_length
  tls_common_name            = var.tls_common_name
  tls_dns_names              = var.tls_dns_names
  tls_validity_hours         = var.tls_validity_hours
  tls_early_renewal_hours    = var.tls_early_renewal_hours
}
