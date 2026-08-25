# Chart `boutique`

Boutique en ligne, deployee sur Kubernetes et administree par Ansible

> Chart généré par forge. Pour le régénérer après modification de la
> spécification : `helm-forge generate --spec forge.yml`.

| | |
|---|---|
| Version du chart | `1.0.0` |
| Version de l'application | `2026.08.1` |
| Kubernetes supporté | `>=1.34.0-0` |
| Environnements | `dev`, `prod` |
| Composants | `api` |

## Installation

Chaque environnement se déploie en superposant son fichier de values à
`values.yaml`. L'ordre des `--values` compte : le dernier gagne.

### dev

```bash
helm upgrade --install boutique ./charts/boutique \
  --namespace boutique-dev --create-namespace \
  --values ./charts/boutique/values.yaml \
  --values ./charts/boutique/values-dev.yaml
```

### prod

```bash
helm upgrade --install boutique ./charts/boutique \
  --namespace boutique-prod --create-namespace \
  --values ./charts/boutique/values.yaml \
  --values ./charts/boutique/values-prod.yaml
```

## Structure du chart

| Fichier | Rôle |
|---|---|
| `Chart.yaml` | Métadonnées : nom, versions, compatibilité Kubernetes. |
| `values.yaml` | Valeurs par défaut, communes à tous les environnements. |
| `values-dev.yaml` | Écarts propres à l'environnement `dev` (namespace `boutique-dev`). |
| `values-prod.yaml` | Écarts propres à l'environnement `prod` (namespace `boutique-prod`). |
| `templates/_helpers.tpl` | Helpers de nommage et d'étiquetage, utilisés partout. |
| `templates/NOTES.txt` | Message affiché après installation. |
| `templates/deployment-api.yaml` | Deployment du composant `api`. |
| `templates/service-api.yaml` | Service du composant `api`. |
| `templates/ingress-api.yaml` | Ingress du composant `api`. |
| `templates/configmap-api.yaml` | ConfigMap du composant `api`. |
| `templates/serviceaccount-api.yaml` | ServiceAccount du composant `api`. |
| `templates/rbac-api.yaml` | Role et RoleBinding du composant `api`. |
| `templates/tests/test-connection.yaml` | Test exécuté par `helm test`. |

## Valeurs

### Globales

| Clé | Défaut | Rôle |
|---|---|---|
| `global.imageRegistry` | `ghcr.io` | Registry commun à tous les composants. |
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
| `api.image.repository` | `acme/boutique` | Dépôt de l'image, sans le registry. |
| `api.image.tag` | `""` | Tag de l'image ; vide, il retombe sur `appVersion`. |
| `api.image.pullPolicy` | `IfNotPresent` | Politique de tirage de l'image. |
| `api.containerPort` | `8080` | Port écouté par le conteneur. |
| `api.portName` | `http` | Nom du port, repris par le Service et les sondes. |
| `api.service.enabled` | `true` | Crée ou non le Service. |
| `api.service.type` | `ClusterIP` | `ClusterIP`, `NodePort` ou `LoadBalancer`. |
| `api.service.port` | `80` | Port exposé par le Service. |
| `api.ingress.enabled` | `true` | Publie ou non le composant hors du cluster. |
| `api.ingress.className` | `nginx` | Controller visé ; ne jamais doubler par l'annotation `kubernetes.io/ingress.class`. |
| `api.ingress.host` | `""` | Hôte servi ; posé par chaque `values-<env>.yaml`, vide l'Ingress est omis. |
| `api.ingress.path` | `/` | Chemin servi par la règle. |
| `api.ingress.pathType` | `Prefix` | `Exact`, `Prefix` ou `ImplementationSpecific` ; champ obligatoire. |
| `api.ingress.tls.enabled` | `true` | Termine TLS ; à `false` le bloc `tls` disparaît entièrement. |
| `api.ingress.tls.issuer` | `letsencrypt-prod` | ClusterIssuer cert-manager émettant le certificat. |
| `api.ingress.tls.secretName` | `""` | Secret portant le certificat ; vide = `<ressource>-tls`. |
| `api.ingress.annotations` | `{}` | Annotations propres au controller. |
| `api.probes.enabled` | `true` | Active les sondes liveness et readiness. |
| `api.probes.liveness.path` | `/healthz` | Chemin HTTP de la sonde liveness. |
| `api.probes.readiness.path` | `/ready` | Chemin HTTP de la sonde readiness. |
| `api.probes.startup.enabled` | `false` | Sonde de démarrage, pour une application lente. |
| `api.resources.requests.cpu` | `50m` | CPU réservé par l'ordonnanceur. |
| `api.resources.requests.memory` | `64Mi` | Mémoire réservée par l'ordonnanceur. |
| `api.resources.limits.cpu` | `200m` | Plafond CPU, au-delà duquel le conteneur est ralenti. |
| `api.resources.limits.memory` | `128Mi` | Plafond mémoire, au-delà duquel le conteneur est tué. |
| `api.podSecurityContext` | voir `values.yaml` | Contexte de sécurité du pod. |
| `api.securityContext` | voir `values.yaml` | Contexte de sécurité du conteneur. |
| `api.nodeSelector` | `{}` | Contrainte de placement sur les nœuds. |
| `api.tolerations` | `[]` | Tolérances aux marquages de nœuds. |
| `api.affinity` | `{}` | Règles d'affinité et d'anti-affinité. |
| `api.extraEnv` | `[]` | Variables d'environnement supplémentaires. |
| `api.config.enabled` | `true` | Crée le ConfigMap et son injection dans le conteneur. |
| `api.config.mountAs` | `env` | `env` (via `envFrom`) ou `file` (monté sous `mountPath`). |
| `api.config.mountPath` | `/etc/api` | Répertoire de montage, en mode `file` uniquement. |
| `api.config.data` | voir `values.yaml` | Clés de configuration ; valeurs toujours écrites en chaînes. |
| `api.serviceAccount.create` | `true` | Crée le compte dédié, ou référence un compte existant. |
| `api.serviceAccount.name` | `""` | Vide = nom dérivé du composant. |
| `api.serviceAccount.annotations` | `{}` | Identité fédérée du fournisseur cloud. |
| `api.serviceAccount.automountServiceAccountToken` | `false` | Monte le jeton d'API dans les pods. |
| `api.rbac.create` | `false` | Crée le Role et son RoleBinding, liés au compte ci-dessus. |
| `api.rbac.rules` | `[]` | Règles du Role ; liste vide = ni Role ni RoleBinding. |

## Vérification

```bash
helm lint ./charts/boutique
helm template boutique ./charts/boutique \
  --values ./charts/boutique/values-dev.yaml | \
  kubeconform -strict -summary -kubernetes-version 1.34.0 -
helm template boutique ./charts/boutique \
  --values ./charts/boutique/values-prod.yaml | \
  kubeconform -strict -summary -kubernetes-version 1.34.0 -
```
