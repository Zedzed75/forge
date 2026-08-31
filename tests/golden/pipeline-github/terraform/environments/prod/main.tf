# =============================================================================
# main.tf — appel du module pour l'environnement « prod »
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
}
