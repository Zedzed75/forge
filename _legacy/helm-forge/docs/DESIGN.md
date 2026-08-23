# helm-forge — Conception (Étape 1)

Document de conception soumis à validation avant écriture du code.
Conventions : voir `CLAUDE.md` (commentaires et documentation en français,
noms de ressources / clés de values / noms de fichiers en anglais).

---

## 1. Questions posées par le CLI

Ordre des questions = ordre ci-dessous. Toute question dont la réponse est
dérivable d'une réponse précédente n'est pas posée (valeur dérivée, modifiable
ensuite dans `forge.yml`).

### 1.1 Identité du projet

| Clé | Question | Défaut | Validation |
|---|---|---|---|
| `app.name` | Nom de l'application | nom du dossier courant, assaini | label DNS-1123, 1 à 40 caractères |
| `app.description` | Description courte | `Chart Helm pour <name>` | 1 à 200 caractères |
| `app.chart_version` | Version du chart | `0.1.0` | SemVer strict |
| `app.app_version` | Version applicative | `1.0.0` | chaîne non vide |
| `app.maintainer_name` | Mainteneur | `git config user.name` | non vide |
| `app.maintainer_email` | Email du mainteneur | `git config user.email` | format email |

Limite de 40 caractères : Kubernetes impose 63 pour un label DNS-1123, et le
générateur suffixe les ressources (`-headless`, `-serviceaccount`, etc.).

### 1.2 Cible Kubernetes et environnements

| Clé | Question | Défaut | Validation |
|---|---|---|---|
| `kubernetes.version` | Version de Kubernetes cible | à confirmer (décision D7) | dans la fenêtre supportée |
| `environments[]` | Environnements (multi-sélection) | `dev`, `prod` | au moins 1, noms uniques, minuscules |
| `namespace_strategy` | Stratégie de namespace | `per_env` | `single`, `per_env` ou `custom` |
| `env.namespace` | Namespace de chaque env (si `custom`) | `<app>-<env>` | label DNS-1123 |
| `create_namespace` | Le chart crée-t-il le namespace ? | non | booléen |

La version de Kubernetes pilote : `kubeVersion` dans `Chart.yaml`, le choix des
`apiVersion` (`autoscaling/v2`, `policy/v1`, `networking.k8s.io/v1`), et le jeu
de schémas utilisé par `kubeconform -strict -kubernetes-version <x.y.z>`.

Défaut `create_namespace = non` : le namespace est presque toujours géré en
amont (Terraform, GitOps, `kubectl create ns`), et le créer dans le chart le
rend supprimable par `helm uninstall`.

### 1.3 Image de conteneur

| Clé | Question | Défaut | Validation |
|---|---|---|---|
| `image.registry` | Registry | `docker.io` (choix : ghcr.io, quay.io, registry.gitlab.com, autre) | hôte RFC 1123 |
| `image.repository` | Dépôt de l'image | `<app.name>` | caractères autorisés OCI |
| `image.tag_strategy` | Tag de l'image | `appVersion` | `appVersion`, `per_env` ou `fixed` |
| `image.pull_policy` | Politique de pull | `IfNotPresent` | `Always`, `IfNotPresent`, `Never` |
| `image.pull_secret` | Secret de pull requis ? | non | booléen, puis nom du secret |

Stratégie `appVersion` : `tag: ""` dans les values, le template retombe sur
`.Chart.AppVersion`. Pratique standard Helm, qui évite la dérive entre
`values.yaml` et `Chart.yaml`.

### 1.4 Composants

| Clé | Question | Défaut | Validation |
|---|---|---|---|
| `components[].name` | Nom du composant | `api` pour le premier | label DNS-1123, unique |
| `components[].kind` | Type de charge de travail | `deployment` | `deployment`, `statefulset`, `cronjob` |
| `components[].addons` | Ressources associées (multi-sélection) | `service`, `configmap` | identifiants du catalogue |

Un projet contient au moins un composant. Le CLI propose « ajouter un autre
composant ? » en boucle (défaut : non après le premier).

### 1.5 Réseau et exposition (par composant exposé)

| Clé | Question | Défaut | Validation |
|---|---|---|---|
| `container_port` | Port du conteneur | `8080` | 1 à 65535 |
| `service.type` | Type de Service | `ClusterIP` | `ClusterIP`, `NodePort`, `LoadBalancer` |
| `service.port` | Port du Service | `80` | 1 à 65535 |
| `ingress.controller` | Ingress controller | `nginx` | `nginx` ou `traefik` |
| `ingress.base_domain` | Domaine de base | `example.com` | sous-domaine RFC 1123 |
| `ingress.host_pattern` | Motif d'hôte | `<app>.<env>.<domaine>`, `<app>.<domaine>` en prod | sous-domaine RFC 1123 après rendu |
| `ingress.path` | Chemin | `/` | commence par `/` |
| `ingress.tls` | TLS activé ? | oui | booléen |
| `ingress.issuer` | ClusterIssuer cert-manager | `letsencrypt-prod` | non vide si TLS |

### 1.6 Santé, ressources, sécurité

| Clé | Question | Défaut | Validation |
|---|---|---|---|
| `probes.enabled` | Sondes liveness et readiness ? | oui | booléen |
| `probes.liveness_path` | Chemin liveness | `/healthz` | commence par `/` |
| `probes.readiness_path` | Chemin readiness | `/ready` | commence par `/` |
| `probes.startup` | Sonde startup ? | non | booléen |
| `resources.profile` | Profil de ressources | `small` | `small`, `medium`, `large`, `custom` |
| `security.strict` | Durcissement strict ? | oui | booléen |

Profils de ressources :

| Profil | CPU requests | Mémoire requests | CPU limits | Mémoire limits |
|---|---|---|---|---|
| `small` | 50m | 64Mi | 200m | 128Mi |
| `medium` | 250m | 256Mi | 1 | 512Mi |
| `large` | 1 | 1Gi | 2 | 2Gi |

`security.strict = oui` génère `runAsNonRoot: true`, `runAsUser: 10001`,
`readOnlyRootFilesystem: true`, `allowPrivilegeEscalation: false`,
`capabilities.drop: [ALL]`, `seccompProfile: RuntimeDefault`, `fsGroup: 10001`.
Tout reste surchargeable dans les values, jamais codé en dur dans le template.

### 1.7 Stockage, configuration, secrets

| Clé | Question | Défaut | Validation |
|---|---|---|---|
| `persistence.enabled` | Volume persistant ? | oui si `statefulset`, sinon non | booléen |
| `persistence.storage_class` | StorageClass | `""` (défaut du cluster) | chaîne |
| `persistence.size` | Taille | `10Gi` | quantité Kubernetes |
| `persistence.access_mode` | Mode d'accès | `ReadWriteOnce` | énumération Kubernetes |
| `persistence.mount_path` | Point de montage | `/data` | chemin absolu |
| `config.keys` | Clés de configuration | `LOG_LEVEL`, `APP_ENV` | majuscules et underscores |
| `secrets.strategy` | Gestion des secrets | `placeholder` | décision D4 |
| `secrets.keys` | Clés de secret | `API_KEY` | majuscules et underscores |

### 1.8 Disponibilité et supervision

| Clé | Question | Défaut | Validation |
|---|---|---|---|
| `hpa.enabled` | Autoscaling horizontal ? | oui (actif en prod uniquement) | booléen |
| `hpa.min` et `hpa.max` | Répliques min et max | `2` et `5` | 1 à 100, min <= max |
| `hpa.target_cpu` | Cible CPU en pourcentage | `80` | 1 à 100 |
| `pdb.enabled` | PodDisruptionBudget ? | oui si HPA actif ou replicas > 1 | booléen |
| `pdb.min_available` | minAvailable | `1` | entier ou pourcentage |
| `networkpolicy.enabled` | NetworkPolicy ? | non | booléen |
| `servicemonitor.enabled` | ServiceMonitor Prometheus ? | non | booléen |
| `servicemonitor.path` | Chemin des métriques | `/metrics` | commence par `/` |
| `rbac.enabled` | ServiceAccount et RBAC ? | oui (SA seul, sans Role par défaut) | booléen |

### 1.9 Extras du projet

| Clé | Question | Défaut | Validation |
|---|---|---|---|
| `extras.makefile` | Générer un Makefile ? | oui | booléen |
| `extras.helmfile` | Générer un helmfile.yaml ? | non (décision D3) | booléen |
| `extras.helm_tests` | Générer `templates/tests/` ? | oui | booléen |
| `extras.ci` | Pipeline CI | `none` | `none`, `github`, `gitlab` |
| `layout` | Disposition du projet | `single` | `single` ou `umbrella` (décision D6) |

### 1.10 Valeurs dérivées par environnement (non demandées)

Le générateur applique un profil par environnement, surchargeable ensuite dans
`values-<env>.yaml` ou directement dans `forge.yml`.

| Environnement | replicas | ressources | HPA | PDB | hôte ingress | log level |
|---|---|---|---|---|---|---|
| `dev` | 1 | profil choisi | non | non | `<app>.dev.<domaine>` | `debug` |
| `staging` | 2 | profil choisi | non | oui | `<app>.staging.<domaine>` | `info` |
| `prod` | 3 | profil choisi, doublé | oui | oui | `<app>.<domaine>` | `info` |
| autre | 1 | profil choisi | non | non | `<app>.<env>.<domaine>` | `info` |

---

## 2. Arborescence générée

### 2.1 Projet mono-chart (recommandé pour la v1)

```
<cible>/
├── forge.yml                       # Spécification rejouable (source de vérité)
├── README.md                       # Doc projet : prérequis, install, upgrade, environnements
├── Makefile                        # Cibles lint / template / validate / install / diff
├── .gitignore                      # Artefacts Helm (*.tgz, charts/*/charts/)
└── charts/
    └── <app>/
        ├── Chart.yaml              # Métadonnées, kubeVersion, appVersion, mainteneurs
        ├── values.yaml             # Valeurs par défaut, chaque bloc commenté
        ├── values-dev.yaml         # Surcharges dev (uniquement les écarts)
        ├── values-prod.yaml        # Surcharges prod (uniquement les écarts)
        ├── .helmignore             # Exclusions du packaging
        ├── README.md               # Doc du chart et tableau des valeurs par composant
        └── templates/
            ├── _helpers.tpl        # name, fullname, chart, labels, selectorLabels, image
            ├── NOTES.txt           # Post-installation : URL, commandes de vérification
            ├── serviceaccount.yaml # ServiceAccount, plus Role et RoleBinding si RBAC
            ├── configmap.yaml      # Configuration non sensible, annotée par checksum
            ├── secret.yaml         # Secret à placeholders, jamais de valeur réelle
            ├── deployment.yaml     # Charge principale : sondes, ressources, securityContext
            ├── statefulset.yaml    # Si kind=statefulset, avec volumeClaimTemplates
            ├── service.yaml        # Service, headless si statefulset
            ├── ingress.yaml        # Ingress nginx ou traefik, TLS optionnel
            ├── hpa.yaml            # HorizontalPodAutoscaler autoscaling/v2
            ├── pdb.yaml            # PodDisruptionBudget policy/v1
            ├── networkpolicy.yaml  # Ingress et egress restreints
            ├── cronjob.yaml        # Si composant de type cronjob
            ├── servicemonitor.yaml # CRD Prometheus Operator, sous garde .Capabilities
            └── tests/
                └── test-connection.yaml  # helm test : appel HTTP du Service
```

Chaque fichier de `templates/` est encadré par `{{- if .Values.<bloc>.enabled }}`,
afin qu'un chart généré avec tous les composants reste installable en n'activant
que ce qui est voulu.

Les fichiers de ressources sont **toujours** suffixés par le nom du composant :
`deployment-api.yaml`, `service-api.yaml`, `deployment-worker.yaml`. Le suffixe
est systématique, y compris pour un chart mono-composant. Deux raisons : la
règle reste unique quel que soit le projet, et ajouter un second composant ne
renomme aucun fichier existant. De la même façon, les values sont toujours
groupées sous une clé portant le nom du composant (`api:`, `worker:`), jamais à
plat, afin que la structure ne change pas selon le nombre de composants.

### 2.2 Projet multi-charts (umbrella)

```
<cible>/
├── forge.yml
├── README.md
├── Makefile
└── charts/
    ├── api/                        # Chart complet et autonome (structure du 2.1)
    ├── worker/                     # Chart complet et autonome
    └── <app>/                      # Chart parapluie
        ├── Chart.yaml              # dependencies: file://../api, file://../worker
        ├── values.yaml             # Un bloc par sous-chart, plus global.*
        ├── values-dev.yaml
        ├── values-prod.yaml
        ├── README.md
        └── templates/
            ├── _helpers.tpl        # Helpers exposés aux sous-charts via global
            └── NOTES.txt
```

Points d'attention umbrella : les valeurs communes passent par `global.*`, les
`_helpers.tpl` ne sont pas hérités par les sous-charts (chacun garde les siens),
et `helm dependency update` doit être joué avant `helm lint`.

**Recommandation : implémenter `single` en premier.** Un chart unique à
plusieurs composants couvre la grande majorité des besoins, se teste plus
simplement, et évite la mécanique `dependency update` dans la boucle de
validation. L'umbrella devient une phase additionnelle après l'étape 5, la
disposition étant déjà présente dans le modèle via le champ `layout`.

---

## 3. Architecture de l'outil

### 3.1 Modules Python

```
src/helm_forge/
├── __init__.py
├── __main__.py               # python -m helm_forge
├── cli.py                    # Typer : new, generate, validate, catalog, golden
├── prompts.py                # questionary : questions vers ProjectSpec (interaction seule)
├── errors.py                 # Exceptions métier converties en codes de sortie CLI
├── models/
│   ├── spec.py               # ProjectSpec et sous-modèles pydantic
│   ├── components.py         # ComponentKind, AddonKind, modèles par composant
│   └── profiles.py           # Profils de ressources et profils par environnement
├── catalog/
│   └── registry.py           # Définition déclarative des composants du catalogue
├── engine/
│   ├── environment.py        # Fabrique d'Environment Jinja2 (délimiteurs [[ ]])
│   ├── filters.py            # Filtres : to_yaml, comment_block, indent_yaml, quantity
│   ├── planner.py            # ProjectSpec vers plan de fichiers (utilisé par --dry-run)
│   ├── renderer.py           # Plan vers FileSet en mémoire, aucune écriture disque
│   └── writer.py             # FileSet vers disque (LF, atomique, ordre stable)
├── spec_io.py                # forge.yml : chargement, sauvegarde, migration de schéma
├── validation/
│   ├── tools.py              # Détection helm et kubeconform, versions, messages d'aide
│   └── runner.py             # helm lint, helm template, kubeconform -strict
└── templates/                # Sources Jinja2, miroir de l'arborescence de sortie
    ├── project/              # README.md.j2, Makefile.j2, gitignore.j2
    ├── chart/                # Chart.yaml.j2, values.yaml.j2, values-env.yaml.j2, README.md.j2
    ├── chart/templates/      # _helpers.tpl.j2, NOTES.txt.j2, deployment.yaml.j2, etc.
    └── partials/
        ├── values/           # Un fragment de values commenté par composant
        ├── readme/           # Une section de README par composant
        └── common/           # En-têtes de fichier, blocs securityContext et probes
```

Séparation des responsabilités : `prompts` ne produit que des données, `planner`
décide seul quels fichiers existent, `renderer` ne fait que rendre, `writer` ne
fait qu'écrire. Le rendu est donc entièrement testable sans toucher au disque.
La limite de 600 lignes par fichier est respectée par construction ; le module
le plus volumineux attendu est `prompts.py`, à découper en sections si besoin.

### 3.2 Modèle de données (esquisse)

```python
class ProjectSpec(BaseModel):
    schema_version: Literal[1] = 1
    app: AppMeta                        # nom, description, versions, mainteneur
    kubernetes: KubernetesTarget        # version, apiVersions dérivées
    layout: Literal["single", "umbrella"] = "single"
    environments: list[EnvironmentSpec]  # au moins 1, noms uniques
    image: ImageSpec
    components: list[ComponentSpec]      # au moins 1, noms uniques
    secrets: SecretSpec
    extras: ExtrasSpec

class ComponentSpec(BaseModel):
    name: str
    kind: ComponentKind                 # deployment, statefulset ou cronjob
    addons: list[AddonKind]             # service, ingress, configmap, hpa, pdb, etc.
    container_port: int = 8080
    service: ServiceSpec | None
    ingress: IngressSpec | None
    probes: ProbesSpec
    resources: ResourcesSpec
    security: SecuritySpec
    persistence: PersistenceSpec | None
    schedule: str | None                # cronjob uniquement

class EnvironmentSpec(BaseModel):
    name: str
    namespace: str
    replicas: dict[str, int]            # par nom de composant
    overrides: dict[str, Any]           # écarts injectés dans values-<env>.yaml
```

Validations croisées dans un `model_validator` : un `ingress` exige un
`service` ; un `hpa` actif interdit un `replicas` figé dans les values ; un
`cronjob` exige un `schedule` ; un `servicemonitor` exige un port nommé.

### 3.3 Garanties de déterminisme

- Aucun horodatage, aucun identifiant aléatoire dans les fichiers générés.
- Tout parcours de collection passe par une liste ordonnée, jamais un `set`.
- Environment Jinja2 configuré avec `trim_blocks`, `lstrip_blocks`,
  `keep_trailing_newline` et `undefined=StrictUndefined` : une variable
  manquante casse le rendu au lieu de produire un vide silencieux.
- Écriture avec `newline="\n"` explicite et encodage UTF-8 sans BOM, quelle que
  soit la plateforme sur laquelle tourne le générateur.
- Test dédié : rendre deux fois la même spec et comparer octet par octet.

### 3.4 Stratégie de tests

| Fichier | Portée |
|---|---|
| `tests/test_models.py` | Règles de validation, valeurs par défaut, erreurs attendues |
| `tests/test_spec_io.py` | Aller-retour `forge.yml` (spec vers YAML vers spec identique) |
| `tests/test_planner.py` | Plan de fichiers par combinaison de composants, `--dry-run` |
| `tests/test_render.py` | Déterminisme, en-tête de commentaire présent dans chaque fichier |
| `tests/test_golden.py` | `tests/specs/*.yml` comparés à `tests/golden/<spec>/` |
| `tests/test_helm.py` | `helm lint`, `helm template` par environnement, `kubeconform -strict` |
| `tests/test_cli.py` | Codes de sortie, messages d'erreur, `--dry-run` sans écriture |

Régénération des golden files : commande `helm-forge golden --update` et cible
`make golden`, avec affichage du diff avant écrasement.

Les tests de `test_helm.py` sont marqués `@pytest.mark.integration` et sautés
avec un message explicite si `helm` ou `kubeconform` est absent. La CI, elle,
les installe et les exige (décision D8).

---

## 4. Décisions ouvertes

| # | Sujet | Recommandation |
|---|---|---|
| D1 | Chart à la racine ou sous `charts/<app>/` | `charts/<app>/` : le passage mono vers multi-charts devient additif, sans déplacement de fichiers. Coût : `helm install ./charts/<app>` au lieu de `helm install ./`. |
| D2 | `values-<env>.yaml` dans le chart ou dans `environments/` | Dans le chart, conformément à `CLAUDE.md`. Ils sont alors packagés dans le `.tgz`, comportement Helm attendu. |
| D3 | Générer un `helmfile.yaml` | Non par défaut, proposé en option. helmfile ajoute un binaire tiers, et le Makefile couvre déjà `upgrade --install -f values-<env>.yaml`. |
| D4 | Stratégie de secrets | Défaut `placeholder` : template `secret.yaml` lisant `.Values.secrets.data`, valeurs vides, marqueur `CHANGEME`, et `required` qui fait échouer le rendu si la valeur n'est pas fournie. Alternatives proposées : `external-secrets`, `sealed-secrets`, `none`. Aucune valeur réelle n'est jamais générée. |
| D5 | Makefile | Oui par défaut, et c'est le point d'entrée principal (`make lint`, `make template ENV=prod`, `make validate`, `make install ENV=dev`). Cible Linux uniquement : aucune contorsion de portabilité, le Makefile utilise `bash` et les outils POSIX sans réserve. Le README documente également les commandes `helm` brutes, à titre de référence. |
| D6 | Umbrella multi-charts | Reporté après l'étape 5, mais le champ `layout` est présent dès le modèle pour éviter une migration de schéma. |
| D7 | Fenêtre de versions Kubernetes supportées | **Tranchée** : dernière version stable, soit `1.36` (stable amont `v1.36.4` au 2026-08-22). Fenêtre supportée `1.34`, `1.35`, `1.36` (N-2 à N), défaut `1.36`. |
| D8 | `helm` et `kubeconform` absents de la machine | **Tranchée et fait** : `helm v4.2.4` (checksum SHA-256 amont vérifié) et `kubeconform v0.8.0` installés dans `~/.local/bin` de WSL Debian, sans `sudo`. Les charts générés restent en `apiVersion: v2`, donc compatibles Helm 3, tout en étant validés par Helm 4. |
| D11 | Plateforme cible | **Tranchée** : Linux uniquement. Les projets générés sont déployés sur des clusters Linux. Aucune concession de portabilité Windows dans les fichiers générés (Makefile, scripts, CI). Le générateur reste du Python portable, mais son environnement de développement et de test de référence est WSL Debian (Python 3.13.5, dépôt accessible via `/mnt/z`). |
| D9 | Sens du mot « composant » | Un composant est une charge de travail nommée (`api`, `worker`, `cron`), portant son `kind` et ses addons. Le catalogue de l'étape 5 devient la liste des addons attachables. Cela réconcilie « composants » (étape 1) et « catalogue de composants » (étape 5). |
| D10 | Langue du README généré | Français, conformément à `CLAUDE.md`. Le README de l'outil lui-même également, par cohérence. |
