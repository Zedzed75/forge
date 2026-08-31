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

service_name = "boutique"
environment  = "prod"
namespace    = "boutique-prod"
labels       = { tier = "frontend" }
kube_context = "plateforme-prod"
quota_cpu    = "4"
quota_memory = "8Gi"
quota_pods   = 30
