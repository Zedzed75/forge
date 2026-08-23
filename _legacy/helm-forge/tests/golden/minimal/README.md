# shop

Boutique en ligne

Projet Kubernetes/Helm généré par [helm-forge](https://github.com/). Tout le
contenu de ce dépôt est reproductible à partir de `forge.yml` :

```bash
helm-forge generate --spec forge.yml --output .
```

## Prérequis

| Outil | Version minimale | Rôle |
|---|---|---|
| `helm` | 3.12 | rendu et déploiement du chart |
| `kubectl` | 1.36 | accès au cluster |
| `kubeconform` | 0.6 | validation stricte des manifestes |
| `make` | 4.0 | raccourcis des opérations courantes |

Cluster cible : Kubernetes `>=1.36.0-0`.

## Environnements

| Environnement | Namespace | Répliques | Fichier de values |
|---|---|---|---|
| `dev` | `shop-dev` | api : 1 | `charts/shop/values-dev.yaml` |
| `prod` | `shop-prod` | api : 3 | `charts/shop/values-prod.yaml` |

## Composants

| Composant | Type | Port | Ressources annexes |
|---|---|---|---|
| `api` | `deployment` | `8080` | `service` |

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
helm template shop ./charts/shop \
  --namespace shop-dev \
  --values ./charts/shop/values.yaml \
  --values ./charts/shop/values-dev.yaml

# Déploiement
helm upgrade --install shop ./charts/shop \
  --namespace shop-dev --create-namespace \
  --values ./charts/shop/values.yaml \
  --values ./charts/shop/values-dev.yaml \
  --wait --timeout 5m
```

Environnement `prod` :

```bash
# Rendu local, sans contact avec le cluster
helm template shop ./charts/shop \
  --namespace shop-prod \
  --values ./charts/shop/values.yaml \
  --values ./charts/shop/values-prod.yaml

# Déploiement
helm upgrade --install shop ./charts/shop \
  --namespace shop-prod --create-namespace \
  --values ./charts/shop/values.yaml \
  --values ./charts/shop/values-prod.yaml \
  --wait --timeout 5m
```

## Validation

Un manifeste rendu doit toujours passer les trois contrôles suivants avant
d'atteindre un cluster :

```bash
# 1. Cohérence du chart
helm lint ./charts/shop

# 2. Rendu effectif de chaque environnement
helm template shop ./charts/shop \
  --values ./charts/shop/values-dev.yaml > /dev/null
helm template shop ./charts/shop \
  --values ./charts/shop/values-prod.yaml > /dev/null

# 3. Conformité aux schémas de l'API Kubernetes 1.36
helm template shop ./charts/shop | \
  kubeconform -strict -summary -kubernetes-version 1.36.0 -
```

## Modifier le projet

Deux voies, selon la nature du changement :

1. **Changement de structure** (ajouter un composant, un environnement, un type
   de ressource) : modifier `forge.yml` puis relancer
   `helm-forge generate --spec forge.yml --output . --force`.
2. **Réglage d'exploitation** (répliques, ressources, hôtes) : modifier
   directement `charts/shop/values-<env>.yaml`.

Attention : une régénération réécrit les fichiers du chart. Les modifications
faites à la main dans `templates/` seront perdues ; portez-les dans `forge.yml`.

## Arborescence

```
.
├── forge.yml                       # spécification, source de vérité
├── Makefile                        # raccourcis lint / template / validate / install
└── charts/shop/
    ├── Chart.yaml                  # métadonnées du chart
    ├── values.yaml                 # valeurs par défaut, entièrement commentées
    ├── values-dev.yaml               # écarts de l'environnement dev
    ├── values-prod.yaml              # écarts de l'environnement prod
    ├── README.md                   # documentation du chart et de ses values
    └── templates/                  # gabarits des ressources Kubernetes
```
