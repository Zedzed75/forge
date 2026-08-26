# =============================================================================
# terraform.tfvars — valeurs de l'environnement « staging »
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
# =============================================================================

service_name    = "boutique"
environment     = "staging"
namespace       = "boutique-staging"
labels          = { tier = "frontend", cost-center = "4210" }
kube_context    = "staging"
quota_cpu       = "4"
quota_memory    = "8Gi"
quota_pods      = 30
tls_dns_names   = ["boutique.staging.example.net"]
tls_common_name = "boutique.staging.example.net"
