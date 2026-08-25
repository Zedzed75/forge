# platform

Plateforme interne de traitement

Projet Kubernetes/Helm généré par [helm-forge](https://github.com/). Tout le
contenu de ce dépôt est reproductible à partir de `forge.yml` :

```bash
helm-forge generate --spec forge.yml --output .
```

## Prérequis

| Outil | Version minimale | Rôle |
|---|---|---|
| `helm` | 3.12 | rendu et déploiement du chart |
| `kubectl` | 1.34 | accès au cluster |
| `kubeconform` | 0.6 | validation stricte des manifestes |
| `make` | 4.0 | raccourcis des opérations courantes |

Cluster cible : Kubernetes `>=1.34.0-0`.

## Environnements

| Environnement | Namespace | Répliques | Fichier de values |
|---|---|---|---|
| `dev` | `platform` | api : 1, worker : 1 | `charts/platform/values-dev.yaml` |
| `staging` | `platform` | api : 2, worker : 2 | `charts/platform/values-staging.yaml` |
| `prod` | `platform` | api : 3, worker : 3 | `charts/platform/values-prod.yaml` |

## Composants

| Composant | Type | Port | Ressources annexes |
|---|---|---|---|
| `api` | `deployment` | `3000` | `service` |
| `worker` | `deployment` | `8080` | aucune |

## Utilisation

### Avec make

```bash
make help                      # liste les cibles disponibles
make lint                      # helm lint sur tous les environnements
make template ENV=dev       # rend les manifestes sans les appliquer
make validate ENV=dev       # rend puis valide avec kubeconform
make validate-all              # valide tous les environnements
make install ENV=dev        # déploie sur l'environnement choisi
```

### Commandes helm brutes

Environnement `dev` :

```bash
# Rendu local, sans contact avec le cluster
helm template platform ./charts/platform \
  --namespace platform \
  --values ./charts/platform/values.yaml \
  --values ./charts/platform/values-dev.yaml

# Déploiement
helm upgrade --install platform ./charts/platform \
  --namespace platform --create-namespace \
  --values ./charts/platform/values.yaml \
  --values ./charts/platform/values-dev.yaml \
  --wait --timeout 5m
```

Environnement `staging` :

```bash
# Rendu local, sans contact avec le cluster
helm template platform ./charts/platform \
  --namespace platform \
  --values ./charts/platform/values.yaml \
  --values ./charts/platform/values-staging.yaml

# Déploiement
helm upgrade --install platform ./charts/platform \
  --namespace platform --create-namespace \
  --values ./charts/platform/values.yaml \
  --values ./charts/platform/values-staging.yaml \
  --wait --timeout 5m
```

Environnement `prod` :

```bash
# Rendu local, sans contact avec le cluster
helm template platform ./charts/platform \
  --namespace platform \
  --values ./charts/platform/values.yaml \
  --values ./charts/platform/values-prod.yaml

# Déploiement
helm upgrade --install platform ./charts/platform \
  --namespace platform --create-namespace \
  --values ./charts/platform/values.yaml \
  --values ./charts/platform/values-prod.yaml \
  --wait --timeout 5m
```

## Validation

Un manifeste rendu doit toujours passer les trois contrôles suivants avant
d'atteindre un cluster :

```bash
# 1. Cohérence du chart
helm lint ./charts/platform

# 2. Rendu effectif de chaque environnement
helm template platform ./charts/platform \
  --values ./charts/platform/values-dev.yaml > /dev/null
helm template platform ./charts/platform \
  --values ./charts/platform/values-staging.yaml > /dev/null
helm template platform ./charts/platform \
  --values ./charts/platform/values-prod.yaml > /dev/null

# 3. Conformité aux schémas de l'API Kubernetes 1.34
helm template platform ./charts/platform | \
  kubeconform -strict -summary -kubernetes-version 1.34.0 -
```

## Modifier le projet

Deux voies, selon la nature du changement :

1. **Changement de structure** (ajouter un composant, un environnement, un type
   de ressource) : modifier `forge.yml` puis relancer
   `helm-forge generate --spec forge.yml --output . --force`.
2. **Réglage d'exploitation** (répliques, ressources, hôtes) : modifier
   directement `charts/platform/values-<env>.yaml`.

Attention : une régénération réécrit les fichiers du chart. Les modifications
faites à la main dans `templates/` seront perdues ; portez-les dans `forge.yml`.

## Arborescence

```
.
├── forge.yml                       # spécification, source de vérité
├── Makefile                        # raccourcis lint / template / validate / install
└── charts/platform/
    ├── Chart.yaml                  # métadonnées du chart
    ├── values.yaml                 # valeurs par défaut, entièrement commentées
    ├── values-dev.yaml               # écarts de l'environnement dev
    ├── values-staging.yaml           # écarts de l'environnement staging
    ├── values-prod.yaml              # écarts de l'environnement prod
    ├── README.md                   # documentation du chart et de ses values
    └── templates/                  # gabarits des ressources Kubernetes
```
