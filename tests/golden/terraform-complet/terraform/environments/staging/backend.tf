# =============================================================================
# backend.tf — où l'état de l'environnement « staging » est conservé
# =============================================================================
# Fichier généré par forge.
#
# L'état Terraform porte EN CLAIR tout ce que les ressources exposent, y compris
# les mots de passe engendrés. Le choix du backend est donc un choix de
# sécurité avant d'être un choix de confort.
#
# La clé d'état est propre à cet environnement : deux racines qui partageraient
# un état se détruiraient mutuellement au premier « apply », et rien dans
# Terraform ne l'annonce à l'avance.
#
# Aucune valeur secrète ici. Les identifiants d'accès au stockage se passent à
# l'initialisation :
#
#   terraform init -backend-config="access_key=..."
#
# ou par les variables d'environnement du fournisseur (AWS_ACCESS_KEY_ID,
# GOOGLE_CREDENTIALS, ARM_CLIENT_SECRET...).
# =============================================================================

terraform {
  backend "s3" {
    bucket  = "etats-terraform-plateforme"
    encrypt = "true"
    key     = "boutique/staging/terraform.tfstate"
    region  = "eu-west-3"
  }
}
