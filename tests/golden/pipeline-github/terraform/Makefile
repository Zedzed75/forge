# =============================================================================
# Makefile — opérations courantes sur le socle Terraform de « boutique »
# =============================================================================
# Fichier généré par forge.
#
# Toutes les cibles acceptent la variable ENV, qui sélectionne la racine
# d'environnement :
#
#   make init  ENV=dev
#   make plan  ENV=prod
#   make apply ENV=prod
#
# Les commandes terraform brutes équivalentes figurent dans le README, pour les
# environnements dépourvus de make.
# =============================================================================

ENVIRONMENTS := dev prod
# Environnement par défaut. Surchargez-le avec ENV=<nom> sur la ligne de commande.
ENV          ?= dev

ROOT         := environments/$(ENV)
MODULE       := modules/boutique

.DEFAULT_GOAL := help
.PHONY: help check-env init plan apply destroy fmt fmt-fix validate lint output clean

help: ## Affiche cette aide
	@echo "Environnements disponibles : $(ENVIRONMENTS)"
	@echo "Environnement courant       : $(ENV)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'

check-env: ## Vérifie que ENV désigne une racine existante
	@test -d "$(ROOT)" || { echo "environnement inconnu : $(ENV) (attendu : $(ENVIRONMENTS))"; exit 1; }

init: check-env ## Initialise la racine (providers et backend d'état)
	terraform -chdir=$(ROOT) init -input=false

plan: check-env ## Montre ce qui serait modifié, sans rien appliquer
	terraform -chdir=$(ROOT) plan -input=false

apply: check-env ## Applique le plan, après confirmation interactive
	terraform -chdir=$(ROOT) apply -input=false

destroy: check-env ## Détruit le socle. ATTENTION : emporte le namespace et TOUT son contenu
	@echo "ATTENTION : la destruction du namespace emporte ce qui y a été déployé"
	@echo "par d'autres outils (charts Helm compris) et que Terraform ignore."
	terraform -chdir=$(ROOT) destroy -input=false

fmt: ## Vérifie la mise en forme canonique de tout le projet
	terraform fmt -check -recursive -diff

fmt-fix: ## Remet tout le projet en forme canonique
	terraform fmt -recursive

validate: check-env ## Valide la configuration de la racine (exige un init préalable)
	terraform -chdir=$(ROOT) validate

lint: ## Passe tflint sur tout le projet
	tflint --recursive

output: check-env ## Affiche les sorties de la racine
	terraform -chdir=$(ROOT) output

clean: ## Supprime les répertoires de travail terraform
	rm -rf $(ROOT)/.terraform $(MODULE)/.terraform
