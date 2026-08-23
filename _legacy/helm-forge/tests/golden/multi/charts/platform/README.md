# Chart `platform`

Plateforme interne de traitement

> Chart généré par helm-forge. Pour le régénérer après modification de la
> spécification : `helm-forge generate --spec forge.yml`.

| | |
|---|---|
| Version du chart | `1.4.2` |
| Version de l'application | `2026.08.1` |
| Kubernetes supporté | `>=1.34.0-0` |
| Environnements | `dev`, `staging`, `prod` |
| Composants | `api`, `worker` |

## Installation

Chaque environnement se déploie en superposant son fichier de values à
`values.yaml`. L'ordre des `--values` compte : le dernier gagne.

### dev

```bash
helm upgrade --install platform ./charts/platform \
  --namespace platform --create-namespace \
  --values ./charts/platform/values.yaml \
  --values ./charts/platform/values-dev.yaml
```

### staging

```bash
helm upgrade --install platform ./charts/platform \
  --namespace platform --create-namespace \
  --values ./charts/platform/values.yaml \
  --values ./charts/platform/values-staging.yaml
```

### prod

```bash
helm upgrade --install platform ./charts/platform \
  --namespace platform --create-namespace \
  --values ./charts/platform/values.yaml \
  --values ./charts/platform/values-prod.yaml
```

## Structure du chart

| Fichier | Rôle |
|---|---|
| `Chart.yaml` | Métadonnées : nom, versions, compatibilité Kubernetes. |
| `values.yaml` | Valeurs par défaut, communes à tous les environnements. |
| `values-dev.yaml` | Écarts propres à l'environnement `dev` (namespace `platform`). |
| `values-staging.yaml` | Écarts propres à l'environnement `staging` (namespace `platform`). |
| `values-prod.yaml` | Écarts propres à l'environnement `prod` (namespace `platform`). |
| `templates/_helpers.tpl` | Helpers de nommage et d'étiquetage, utilisés partout. |
| `templates/NOTES.txt` | Message affiché après installation. |
| `templates/deployment-api.yaml` | Deployment du composant `api`. |
| `templates/service-api.yaml` | Service du composant `api`. |
| `templates/deployment-worker.yaml` | Deployment du composant `worker`. |
| `templates/tests/test-connection.yaml` | Test exécuté par `helm test`. |

## Valeurs

### Globales

| Clé | Défaut | Rôle |
|---|---|---|
| `global.imageRegistry` | `registry.gitlab.com` | Registry commun à tous les composants. |
| `global.imagePullSecrets` | `[]` | Secrets de tirage pour un registry privé. |
| `global.environment` | `""` | Nom de l'environnement, posé en label sur les ressources. |
| `nameOverride` | `""` | Remplace le nom du chart dans les noms composés. |
| `fullnameOverride` | `""` | Remplace intégralement le nom des ressources. |

### Composant `api`

Type : `deployment`
| Clé | Défaut | Rôle |
|---|---|---|
| `api.enabled` | `true` | Active ou désactive entièrement le composant. |
| `api.replicaCount` | `1` | Nombre de répliques, surchargé par environnement. |
| `api.image.repository` | `acme/platform` | Dépôt de l'image, sans le registry. |
| `api.image.tag` | `""` | Tag de l'image ; vide, il retombe sur `appVersion`. |
| `api.image.pullPolicy` | `Always` | Politique de tirage de l'image. |
| `api.containerPort` | `3000` | Port écouté par le conteneur. |
| `api.portName` | `http` | Nom du port, repris par le Service et les sondes. |
| `api.service.enabled` | `true` | Crée ou non le Service. |
| `api.service.type` | `LoadBalancer` | `ClusterIP`, `NodePort` ou `LoadBalancer`. |
| `api.service.port` | `8080` | Port exposé par le Service. |
| `api.probes.enabled` | `true` | Active les sondes liveness et readiness. |
| `api.probes.liveness.path` | `/healthz` | Chemin HTTP de la sonde liveness. |
| `api.probes.readiness.path` | `/ready` | Chemin HTTP de la sonde readiness. |
| `api.probes.startup.enabled` | `true` | Sonde de démarrage, pour une application lente. |
| `api.resources.requests.cpu` | `250m` | CPU réservé par l'ordonnanceur. |
| `api.resources.requests.memory` | `256Mi` | Mémoire réservée par l'ordonnanceur. |
| `api.resources.limits.cpu` | `1` | Plafond CPU, au-delà duquel le conteneur est ralenti. |
| `api.resources.limits.memory` | `512Mi` | Plafond mémoire, au-delà duquel le conteneur est tué. |
| `api.podSecurityContext` | voir `values.yaml` | Contexte de sécurité du pod. |
| `api.securityContext` | voir `values.yaml` | Contexte de sécurité du conteneur. |
| `api.nodeSelector` | `{}` | Contrainte de placement sur les nœuds. |
| `api.tolerations` | `[]` | Tolérances aux marquages de nœuds. |
| `api.affinity` | `{}` | Règles d'affinité et d'anti-affinité. |
| `api.extraEnv` | `[]` | Variables d'environnement supplémentaires. |

### Composant `worker`

Type : `deployment` — commande : `/app/bin/worker`
| Clé | Défaut | Rôle |
|---|---|---|
| `worker.enabled` | `true` | Active ou désactive entièrement le composant. |
| `worker.replicaCount` | `2` | Nombre de répliques, surchargé par environnement. |
| `worker.image.repository` | `acme/platform` | Dépôt de l'image, sans le registry. |
| `worker.image.tag` | `""` | Tag de l'image ; vide, il retombe sur `appVersion`. |
| `worker.image.pullPolicy` | `Always` | Politique de tirage de l'image. |
| `worker.containerPort` | `8080` | Port écouté par le conteneur. |
| `worker.portName` | `http` | Nom du port, repris par le Service et les sondes. |
| `worker.probes.enabled` | `false` | Active les sondes liveness et readiness. |
| `worker.probes.liveness.path` | `/healthz` | Chemin HTTP de la sonde liveness. |
| `worker.probes.readiness.path` | `/ready` | Chemin HTTP de la sonde readiness. |
| `worker.probes.startup.enabled` | `false` | Sonde de démarrage, pour une application lente. |
| `worker.resources.requests.cpu` | `50m` | CPU réservé par l'ordonnanceur. |
| `worker.resources.requests.memory` | `64Mi` | Mémoire réservée par l'ordonnanceur. |
| `worker.resources.limits.cpu` | `200m` | Plafond CPU, au-delà duquel le conteneur est ralenti. |
| `worker.resources.limits.memory` | `128Mi` | Plafond mémoire, au-delà duquel le conteneur est tué. |
| `worker.podSecurityContext` | voir `values.yaml` | Contexte de sécurité du pod. |
| `worker.securityContext` | voir `values.yaml` | Contexte de sécurité du conteneur. |
| `worker.nodeSelector` | `{}` | Contrainte de placement sur les nœuds. |
| `worker.tolerations` | `[]` | Tolérances aux marquages de nœuds. |
| `worker.affinity` | `{}` | Règles d'affinité et d'anti-affinité. |
| `worker.extraEnv` | `[]` | Variables d'environnement supplémentaires. |

## Vérification

```bash
helm lint ./charts/platform
helm template platform ./charts/platform \
  --values ./charts/platform/values-dev.yaml | \
  kubeconform -strict -summary -kubernetes-version 1.34.0 -
helm template platform ./charts/platform \
  --values ./charts/platform/values-staging.yaml | \
  kubeconform -strict -summary -kubernetes-version 1.34.0 -
helm template platform ./charts/platform \
  --values ./charts/platform/values-prod.yaml | \
  kubeconform -strict -summary -kubernetes-version 1.34.0 -
```
