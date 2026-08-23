# =============================================================================
# Makefile — opérations courantes sur le chart « shop »
# =============================================================================
# Fichier généré par helm-forge.
#
# Toutes les cibles acceptent la variable ENV, qui sélectionne l'environnement
# et son namespace :
#
#   make lint
#   make template ENV=dev
#   make validate ENV=prod
#   make install  ENV=dev
#
# Les commandes helm brutes équivalentes figurent dans le README, pour les
# environnements dépourvus de make.
# =============================================================================

CHART           := charts/shop
RELEASE         := shop
KUBE_VERSION    := 1.36.0
ENVIRONMENTS    := dev prod
# Environnement par défaut. Surchargez-le avec ENV=<nom> sur la ligne de commande.
ENV             ?= dev

# Namespace associé à chaque environnement, figé à la génération.
NAMESPACE_dev := shop-dev
NAMESPACE_prod := shop-prod
NAMESPACE       := $(NAMESPACE_$(ENV))

# Superposition des fichiers de values : le dernier l'emporte.
VALUES          := --values $(CHART)/values.yaml --values $(CHART)/values-$(ENV).yaml

.DEFAULT_GOAL := help
.PHONY: help lint template validate validate-all install upgrade uninstall diff test package clean

help: ## Affiche cette aide
	@echo "Cibles disponibles :"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Environnements : $(ENVIRONMENTS)  (courant : $(ENV) -> namespace $(NAMESPACE))"

check-env: ## Vérifie que ENV désigne un environnement connu
	@if [ -z "$(NAMESPACE)" ]; then \
		echo "ENV='$(ENV)' inconnu. Valeurs acceptées : $(ENVIRONMENTS)"; \
		exit 1; \
	fi

lint: ## Analyse statique du chart pour chaque environnement
	@for env in $(ENVIRONMENTS); do \
		echo "--- helm lint ($$env) ---"; \
		helm lint $(CHART) \
			--values $(CHART)/values.yaml \
			--values $(CHART)/values-$$env.yaml || exit 1; \
	done

template: check-env ## Rend les manifestes de l'environnement ENV sur la sortie standard
	@helm template $(RELEASE) $(CHART) \
		--namespace $(NAMESPACE) $(VALUES)

validate: check-env ## Rend puis valide les manifestes de ENV avec kubeconform
	@echo "--- kubeconform ($(ENV), Kubernetes $(KUBE_VERSION)) ---"
	@helm template $(RELEASE) $(CHART) \
		--namespace $(NAMESPACE) $(VALUES) | \
		kubeconform -strict -summary \
			-kubernetes-version $(KUBE_VERSION) \
			-schema-location default -

validate-all: ## Valide tous les environnements
	@for env in $(ENVIRONMENTS); do \
		$(MAKE) --no-print-directory validate ENV=$$env || exit 1; \
	done

install: check-env ## Installe ou met à jour la release dans le namespace de ENV
	helm upgrade --install $(RELEASE) $(CHART) \
		--namespace $(NAMESPACE) --create-namespace $(VALUES) \
		--wait --timeout 5m

upgrade: install ## Alias de install (helm upgrade --install)

diff: check-env ## Montre l'écart entre la release en place et le chart local
	@helm diff upgrade $(RELEASE) $(CHART) \
		--namespace $(NAMESPACE) $(VALUES) || \
		echo "Le plugin helm-diff est absent : helm plugin install https://github.com/databus23/helm-diff"

test: check-env ## Exécute les tests embarqués dans le chart
	helm test $(RELEASE) --namespace $(NAMESPACE)

uninstall: check-env ## Supprime la release de l'environnement ENV
	helm uninstall $(RELEASE) --namespace $(NAMESPACE)

package: ## Construit l'archive .tgz du chart
	helm package $(CHART) --destination dist/

clean: ## Supprime les artefacts locaux
	rm -rf dist/
