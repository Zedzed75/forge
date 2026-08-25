# boutique

Boutique en ligne, deployee sur Kubernetes et administree par Ansible

Projet Kubernetes/Helm généré par [forge](https://github.com/). Tout le
contenu de ce dépôt est reproductible à partir de `forge.yml` :

```bash
forge generate
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
| `dev` | `boutique-dev` | api : 1 | `charts/boutique/values-dev.yaml` |
| `prod` | `boutique-prod` | api : 3 | `charts/boutique/values-prod.yaml` |

## Composants

| Composant | Type | Port | Ressources annexes |
|---|---|---|---|
| `api` | `deployment` | `8080` | `service`, `ingress`, `configmap`, `serviceaccount` |

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
helm template boutique ./charts/boutique \
  --namespace boutique-dev \
  --values ./charts/boutique/values.yaml \
  --values ./charts/boutique/values-dev.yaml

# Déploiement
helm upgrade --install boutique ./charts/boutique \
  --namespace boutique-dev --create-namespace \
  --values ./charts/boutique/values.yaml \
  --values ./charts/boutique/values-dev.yaml \
  --wait --timeout 5m
```

Environnement `prod` :

```bash
# Rendu local, sans contact avec le cluster
helm template boutique ./charts/boutique \
  --namespace boutique-prod \
  --values ./charts/boutique/values.yaml \
  --values ./charts/boutique/values-prod.yaml

# Déploiement
helm upgrade --install boutique ./charts/boutique \
  --namespace boutique-prod --create-namespace \
  --values ./charts/boutique/values.yaml \
  --values ./charts/boutique/values-prod.yaml \
  --wait --timeout 5m
```

## Validation

Un manifeste rendu doit toujours passer les trois contrôles suivants avant
d'atteindre un cluster :

```bash
# 1. Cohérence du chart
helm lint ./charts/boutique

# 2. Rendu effectif de chaque environnement
helm template boutique ./charts/boutique \
  --values ./charts/boutique/values-dev.yaml > /dev/null
helm template boutique ./charts/boutique \
  --values ./charts/boutique/values-prod.yaml > /dev/null

# 3. Conformité aux schémas de l'API Kubernetes 1.34
helm template boutique ./charts/boutique | \
  kubeconform -strict -summary -kubernetes-version 1.34.0 -
```

## Modifier le projet

Deux voies, selon la nature du changement :

1. **Changement de structure** (ajouter un composant, un environnement, un type
   de ressource) : modifier `forge.yml` puis relancer
   `forge generate --force`.
2. **Réglage d'exploitation** (répliques, ressources, hôtes) : modifier
   directement `charts/boutique/values-<env>.yaml`.

Attention : une régénération réécrit les fichiers du chart. Les modifications
faites à la main dans `templates/` seront perdues ; portez-les dans `forge.yml`.

## Arborescence

```
.
├── forge.yml                       # spécification, source de vérité
├── Makefile                        # raccourcis lint / template / validate / install
└── charts/boutique/
    ├── Chart.yaml                  # métadonnées du chart
    ├── values.yaml                 # valeurs par défaut, entièrement commentées
    ├── values-dev.yaml               # écarts de l'environnement dev
    ├── values-prod.yaml              # écarts de l'environnement prod
    ├── README.md                   # documentation du chart et de ses values
    └── templates/                  # gabarits des ressources Kubernetes
```
