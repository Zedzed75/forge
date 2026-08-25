# Chart `boutique`

Boutique en ligne, chart complet

> Chart généré par forge. Pour le régénérer après modification de la
> spécification : `helm-forge generate --spec forge.yml`.

| | |
|---|---|
| Version du chart | `1.2.0` |
| Version de l'application | `2026.08.1` |
| Kubernetes supporté | `>=1.34.0-0` |
| Environnements | `dev`, `prod` |
| Composants | `api`, `db-proxy`, `cleanup` |

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
| `templates/secret-api.yaml` | Secret du composant `api`. |
| `templates/hpa-api.yaml` | HorizontalPodAutoscaler du composant `api`. |
| `templates/pdb-api.yaml` | PodDisruptionBudget du composant `api`. |
| `templates/serviceaccount-api.yaml` | ServiceAccount du composant `api`. |
| `templates/rbac-api.yaml` | Role et RoleBinding du composant `api`. |
| `templates/networkpolicy-api.yaml` | NetworkPolicy du composant `api`. |
| `templates/statefulset-db-proxy.yaml` | StatefulSet du composant `db-proxy`. |
| `templates/service-db-proxy.yaml` | Service du composant `db-proxy`. |
| `templates/configmap-db-proxy.yaml` | ConfigMap du composant `db-proxy`. |
| `templates/serviceaccount-db-proxy.yaml` | ServiceAccount du composant `db-proxy`. |
| `templates/rbac-db-proxy.yaml` | Role et RoleBinding du composant `db-proxy`. |
| `templates/cronjob-cleanup.yaml` | CronJob du composant `cleanup`. |
| `templates/configmap-cleanup.yaml` | ConfigMap du composant `cleanup`. |
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
| `api.secret.enabled` | `false` | Crée l'emplacement de secret ; aucune valeur n'est jamais générée. |
| `api.secret.create` | `true` | À `false`, le chart référence `existingSecret` au lieu de créer. |
| `api.secret.existingSecret` | `""` | Secret géré hors du chart ; obligatoire quand `create` vaut `false`. |
| `api.secret.type` | `Opaque` | Type de Secret ; un type spécialisé impose ses propres clés. |
| `api.secret.mountAs` | `env` | `env` (via `envFrom`) ou `file` (monté sous `mountPath`). |
| `api.secret.stringData` | voir `values.yaml` | Clés attendues, en clair ; jamais de bloc `data` en base64 à côté. |
| `api.hpa.enabled` | `false` | Autoscaling ; posé par le profil de chaque environnement. |
| `api.hpa.minReplicas` | `2` | Plancher de répliques. |
| `api.hpa.maxReplicas` | `5` | Plafond de répliques. |
| `api.hpa.targetCPUUtilizationPercentage` | `80` | Cible CPU en pourcent ; entier obligatoire. |
| `api.hpa.targetMemoryUtilizationPercentage` | `null` | Cible mémoire ; `null` = mémoire non surveillée. |
| `api.pdb.enabled` | `false` | Budget d'interruption ; posé par le profil de chaque environnement. |
| `api.pdb.minAvailable` | `1` | Entier ou pourcentage ; exclusif de `maxUnavailable`. |
| `api.serviceAccount.create` | `true` | Crée le compte dédié, ou référence un compte existant. |
| `api.serviceAccount.name` | `""` | Vide = nom dérivé du composant. |
| `api.serviceAccount.annotations` | `{}` | Identité fédérée du fournisseur cloud. |
| `api.serviceAccount.automountServiceAccountToken` | `false` | Monte le jeton d'API dans les pods. |
| `api.rbac.create` | `false` | Crée le Role et son RoleBinding, liés au compte ci-dessus. |
| `api.rbac.rules` | `[]` | Règles du Role ; liste vide = ni Role ni RoleBinding. |
| `api.networkPolicy.enabled` | `false` | Applique le cloisonnement réseau. |
| `api.networkPolicy.allowFromSameNamespace` | `true` | Trafic entrant venant du namespace du composant. |
| `api.networkPolicy.allowFromNamespaces` | `[]` | Namespaces autorisés en entrée, par nom. |
| `api.networkPolicy.allowDNS` | `true` | Autorise la résolution de noms sortante. |
| `api.networkPolicy.allowEgressAll` | `false` | Autorise tout le trafic sortant. |

### Composant `db-proxy`

Type : `statefulset`
| Clé | Défaut | Rôle |
|---|---|---|
| `db-proxy.enabled` | `true` | Active ou désactive entièrement le composant. |
| `db-proxy.replicaCount` | `1` | Nombre de répliques, surchargé par environnement. |
| `db-proxy.image.repository` | `acme/boutique` | Dépôt de l'image, sans le registry. |
| `db-proxy.image.tag` | `""` | Tag de l'image ; vide, il retombe sur `appVersion`. |
| `db-proxy.image.pullPolicy` | `IfNotPresent` | Politique de tirage de l'image. |
| `db-proxy.containerPort` | `5432` | Port écouté par le conteneur. |
| `db-proxy.portName` | `postgres` | Nom du port, repris par le Service et les sondes. |
| `db-proxy.service.enabled` | `true` | Crée ou non le Service. |
| `db-proxy.service.type` | `ClusterIP` | `ClusterIP`, `NodePort` ou `LoadBalancer`. |
| `db-proxy.service.port` | `80` | Port exposé par le Service. |
| `db-proxy.probes.enabled` | `true` | Active les sondes liveness et readiness. |
| `db-proxy.probes.liveness.path` | `/healthz` | Chemin HTTP de la sonde liveness. |
| `db-proxy.probes.readiness.path` | `/ready` | Chemin HTTP de la sonde readiness. |
| `db-proxy.probes.startup.enabled` | `false` | Sonde de démarrage, pour une application lente. |
| `db-proxy.resources.requests.cpu` | `50m` | CPU réservé par l'ordonnanceur. |
| `db-proxy.resources.requests.memory` | `64Mi` | Mémoire réservée par l'ordonnanceur. |
| `db-proxy.resources.limits.cpu` | `200m` | Plafond CPU, au-delà duquel le conteneur est ralenti. |
| `db-proxy.resources.limits.memory` | `128Mi` | Plafond mémoire, au-delà duquel le conteneur est tué. |
| `db-proxy.podSecurityContext` | voir `values.yaml` | Contexte de sécurité du pod. |
| `db-proxy.securityContext` | voir `values.yaml` | Contexte de sécurité du conteneur. |
| `db-proxy.nodeSelector` | `{}` | Contrainte de placement sur les nœuds. |
| `db-proxy.tolerations` | `[]` | Tolérances aux marquages de nœuds. |
| `db-proxy.affinity` | `{}` | Règles d'affinité et d'anti-affinité. |
| `db-proxy.extraEnv` | `[]` | Variables d'environnement supplémentaires. |
| `db-proxy.config.enabled` | `true` | Crée le ConfigMap et son injection dans le conteneur. |
| `db-proxy.config.mountAs` | `file` | `env` (via `envFrom`) ou `file` (monté sous `mountPath`). |
| `db-proxy.config.mountPath` | `/etc/db-proxy` | Répertoire de montage, en mode `file` uniquement. |
| `db-proxy.config.data` | voir `values.yaml` | Clés de configuration ; valeurs toujours écrites en chaînes. |
| `db-proxy.persistence.enabled` | `true` | Attache un volume par pod. |
| `db-proxy.persistence.size` | `20Gi` | Taille demandée — **immuable** après installation. |
| `db-proxy.persistence.storageClass` | `""` | Vide = classe par défaut du cluster ; la clé est alors omise. |
| `db-proxy.persistence.accessMode` | `ReadWriteOnce` | `ReadWriteOnce`, `ReadOnlyMany`, `ReadWriteMany` ou `ReadWriteOncePod`. |
| `db-proxy.persistence.mountPath` | `/data` | Chemin de montage du volume dans le conteneur. |
| `db-proxy.updateStrategy.type` | `RollingUpdate` | `RollingUpdate` ou `OnDelete`. |
| `db-proxy.updateStrategy.partition` | `0` | Ordinal à partir duquel les pods sont mis à jour. |
| `db-proxy.podManagementPolicy` | absent | `OrderedReady` (défaut de Kubernetes) ou `Parallel` ; **immuable**. |
| `db-proxy.serviceAccount.create` | `true` | Crée le compte dédié, ou référence un compte existant. |
| `db-proxy.serviceAccount.name` | `""` | Vide = nom dérivé du composant. |
| `db-proxy.serviceAccount.annotations` | `{}` | Identité fédérée du fournisseur cloud. |
| `db-proxy.serviceAccount.automountServiceAccountToken` | `false` | Monte le jeton d'API dans les pods. |
| `db-proxy.rbac.create` | `false` | Crée le Role et son RoleBinding, liés au compte ci-dessus. |
| `db-proxy.rbac.rules` | `[]` | Règles du Role ; liste vide = ni Role ni RoleBinding. |

### Composant `cleanup`

Type : `cronjob`
| Clé | Défaut | Rôle |
|---|---|---|
| `cleanup.enabled` | `true` | Active ou désactive entièrement le composant. |
| `cleanup.replicaCount` | `1` | Nombre de répliques, surchargé par environnement. |
| `cleanup.image.repository` | `acme/boutique` | Dépôt de l'image, sans le registry. |
| `cleanup.image.tag` | `""` | Tag de l'image ; vide, il retombe sur `appVersion`. |
| `cleanup.image.pullPolicy` | `IfNotPresent` | Politique de tirage de l'image. |
| `cleanup.containerPort` | `8080` | Port écouté par le conteneur. |
| `cleanup.portName` | `http` | Nom du port, repris par le Service et les sondes. |
| `cleanup.probes.enabled` | `true` | Active les sondes liveness et readiness. |
| `cleanup.probes.liveness.path` | `/healthz` | Chemin HTTP de la sonde liveness. |
| `cleanup.probes.readiness.path` | `/ready` | Chemin HTTP de la sonde readiness. |
| `cleanup.probes.startup.enabled` | `false` | Sonde de démarrage, pour une application lente. |
| `cleanup.resources.requests.cpu` | `50m` | CPU réservé par l'ordonnanceur. |
| `cleanup.resources.requests.memory` | `64Mi` | Mémoire réservée par l'ordonnanceur. |
| `cleanup.resources.limits.cpu` | `200m` | Plafond CPU, au-delà duquel le conteneur est ralenti. |
| `cleanup.resources.limits.memory` | `128Mi` | Plafond mémoire, au-delà duquel le conteneur est tué. |
| `cleanup.podSecurityContext` | voir `values.yaml` | Contexte de sécurité du pod. |
| `cleanup.securityContext` | voir `values.yaml` | Contexte de sécurité du conteneur. |
| `cleanup.nodeSelector` | `{}` | Contrainte de placement sur les nœuds. |
| `cleanup.tolerations` | `[]` | Tolérances aux marquages de nœuds. |
| `cleanup.affinity` | `{}` | Règles d'affinité et d'anti-affinité. |
| `cleanup.extraEnv` | `[]` | Variables d'environnement supplémentaires. |
| `cleanup.config.enabled` | `true` | Crée le ConfigMap et son injection dans le conteneur. |
| `cleanup.config.mountAs` | `env` | `env` (via `envFrom`) ou `file` (monté sous `mountPath`). |
| `cleanup.config.mountPath` | `/etc/cleanup` | Répertoire de montage, en mode `file` uniquement. |
| `cleanup.config.data` | voir `values.yaml` | Clés de configuration ; valeurs toujours écrites en chaînes. |
| `cleanup.cron.schedule` | `0 3 * * *` | Planification cron à cinq champs. |
| `cleanup.cron.concurrencyPolicy` | `Forbid` | `Allow`, `Forbid` ou `Replace`. |
| `cleanup.cron.restartPolicy` | `OnFailure` | `OnFailure` ou `Never` ; `Always` est refusé par l'API. |
| `cleanup.cron.timeZone` | `""` | Fuseau IANA ; vide, la clé est omise du manifeste. |
| `cleanup.cron.suspend` | `false` | Suspend les déclenchements sans supprimer l'objet. |
| `cleanup.cron.successfulJobsHistoryLimit` | `3` | Exécutions réussies conservées. |
| `cleanup.cron.failedJobsHistoryLimit` | `1` | Exécutions échouées conservées. |
| `cleanup.cron.backoffLimit` | `3` | Reprises avant d'abandonner une exécution. |
| `cleanup.cron.startingDeadlineSeconds` | `null` | Retard toléré ; `null` = rattrapage sans limite. |

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
