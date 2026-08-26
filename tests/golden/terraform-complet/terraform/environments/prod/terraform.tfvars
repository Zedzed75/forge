# =============================================================================
# terraform.tfvars — valeurs de l'environnement « prod »
# =============================================================================
# Fichier généré par forge, chargé automatiquement par Terraform.
#
# AUCUNE VALEUR SECRÈTE ICI, et ce n'est pas un oubli : un fichier de ce nom
# finit versionné. Les variables secrètes n'ont pas de valeur par défaut et se
# fournissent par TF_VAR_<nom> — la CI les tire de son coffre, jamais du dépôt.
#
# Toute variable déclarée dans variables.tf peut être ajoutée ici, même celles
# que forge n'a pas pré-remplies. En revanche, une variable NON déclarée fait
# échouer Terraform : ce fichier n'est pas un endroit où noter des paramètres.
#
# Environnement de PRODUCTION.
# =============================================================================

service_name    = "boutique"
environment     = "prod"
namespace       = "boutique-prod"
labels          = { tier = "frontend", cost-center = "4210", criticality = "high" }
kube_context    = "plateforme-prod-eu-west-3"
quota_cpu       = "16"
quota_memory    = "32Gi"
quota_pods      = 120
tls_dns_names   = ["boutique.example.net"]
tls_common_name = "boutique.example.net"
