# DESIGN.md — architecture de forge

Livrable de la phase 1. Toutes les affirmations sur le comportement de copier
ont été **vérifiées expérimentalement** (copier 9.17.2) ; les constats bruts
sont consignés dans `MIGRATION.md` §2.

---

## 1. Vue d'ensemble

```
forge.yml  ──►  cœur : chargement + validation (pydantic assemblé depuis les plugins)
                  │
                  ├─ pour chaque domaine retenu ──► hook forge_answers ──► copier.run_copy
                  │        (src = racine du dépôt forge, _subdirectory = gabarit du plugin)
                  │                                          │
                  │                                          ▼
                  │                                  <cible>/<domaine>/…
                  │                                  + .copier-answers.yml
                  │
                  ├─ forge validate ──► hook forge_validators ──► runner du cœur (subprocess/WSL)
                  ├─ forge validate ──► hook forge_projection  ──► contrôles inter-domaines (cœur)
                  └─ forge update   ──► copier.run_update par domaine
```

Le cœur ne connaît que : des specs, un répertoire de gabarit, un dict de données,
des commandes externes et des projections. Il n'a aucune notion de SSH, de rôle,
de namespace ou de chart.

---

## 2. Contrat de plugin (pluggy)

### 2.1 Types échangés

```python
# forge/plugins_api/types.py

@dataclass(frozen=True)
class DomainInfo:
    """Identité d'un domaine généré."""
    name: str          # "ansible" — clé de section dans forge.yml et nom de plugin
    title: str         # "Ansible" — affichage
    summary: str       # une ligne, pour `forge plugins`
    outdir: str        # sous-répertoire de sortie, par défaut == name

@dataclass(frozen=True)
class Command:
    """Une commande de validation externe déclarée par un plugin."""
    label: str                       # "helm lint (prod)" — repris tel quel dans le rapport
    tool: str                        # binaire à localiser ("helm", "ansible-lint")
    argv: list[str]                  # arguments, sans le binaire
    cwd: Path | None = None          # défaut : répertoire du domaine
    env: tuple[tuple[str, str], ...] = ()  # variables d'environnement (phase 3, R1)
    stdin_from: str | None = None    # label d'une commande dont stdout alimente ce stdin
    timeout: int = 300
    install_hint: str = ""           # message affiché si le binaire est absent
    requires_linux: bool = False     # autorise le repli WSL sous Windows

@dataclass(frozen=True)
class Issue:
    """Un constat de validation inter-domaines."""
    level: Literal["error", "warning"]
    message: str                     # phrase actionnable
    hint: str = ""                   # correction suggérée
    domains: tuple[str, ...] = ()    # domaines concernés

@dataclass(frozen=True)
class Projection:
    """Ce qu'un domaine affirme avoir produit, exprimé sans vocabulaire de domaine.

    Le cœur compare les projections entre elles : deux domaines qui déclarent la
    même facette doivent déclarer la même valeur. C'est ce mécanisme — et non des
    règles « si ansible alors… » — qui implémente les contrôles inter-domaines.
    """
    service_name: str
    environments: tuple[str, ...]   # ceux que le domaine MATÉRIALISE (phase 5),
                                    # pas une recopie de service.environments
    labels: dict[str, str] = field(default_factory=dict)
    facets: dict[str, tuple[str, ...]] = field(default_factory=dict)
    # ex. ansible → {"inventory_hosts": (...), "groups": (...)}
    #     helm    → {"namespaces": (...), "ingress_hosts": (...)}
    #
    # Le nom d'une facette appartient à un VOCABULAIRE PARTAGÉ entre domaines
    # (`forge.validate.consistency.FACET_VOCABULARY`) : deux domaines qui
    # emploient le même nom affirment parler de la même chose. Une facette hors
    # vocabulaire n'est comparée à personne.
    #
    # Corrigé en phase 5 : cette section proposait `hosts` pour les deux
    # domaines, en supposant que même nom = même sens. Ansible entendait par là
    # ses machines d'inventaire, Helm ses hôtes d'Ingress — et `forge validate`
    # échouait sur toute spécification à deux domaines. C'est le premier défaut
    # qu'a révélé la rencontre de deux domaines réels.
```

### 2.2 Hookspecs

```python
# forge/plugins_api/hookspecs.py
hookspec = pluggy.HookspecMarker("forge")

@hookspec
def forge_domain() -> DomainInfo:
    """Identité du domaine. Seul hook obligatoire pour être découvert."""

@hookspec
def forge_spec_model() -> type[BaseModel]:
    """Sous-modèle pydantic validant la section <domaine> de forge.yml.

    Le cœur assemble le modèle racine à partir des sous-modèles enregistrés :
    chaque section est optionnelle, l'absence de section signifie « domaine non
    généré ». Aucune connaissance du contenu côté cœur.
    """

@hookspec
def forge_interview(prompter: Prompter, service: ServiceSpec) -> dict[str, Any] | None:
    """Conduit l'entretien du domaine et retourne sa section de forge.yml.

    Le plugin pilote son propre questionnaire à travers le protocole `Prompter`
    fourni par le cœur (text/confirm/select/checkbox/note), jamais questionary
    directement : c'est ce qui rend l'entretien rejouable en test.
    Retourne None si l'utilisateur décline le domaine.
    """

@hookspec
def forge_template_subdir() -> str:
    """Chemin du gabarit copier, relatif à la racine du dépôt forge.

    Exemple : "src/forge/plugins/ansible/template".
    Passé à copier via `_subdirectory` (cf. §5).
    """

@hookspec
def forge_answers(spec: ForgeSpec) -> dict[str, Any]:
    """Projette la spec unifiée vers le dict `domain` passé à copier.

    Sortie JSON-sérialisable et **déterministe** (ordre des clés figé) : elle est
    écrite telle quelle dans `.copier-answers.yml` et rejouée par `copier update`.
    """

@hookspec
def forge_validators(spec: ForgeSpec, outdir: Path) -> list[Command]:
    """Commandes externes validant le domaine généré, dans l'ordre d'exécution."""

@hookspec
def forge_projection(spec: ForgeSpec) -> Projection:
    """Ce que le domaine affirme produire, pour les contrôles inter-domaines."""

@hookspec
def forge_check_spec(spec: ForgeSpec) -> list[Issue]:
    """Contrôles croisés sur la **spécification**, avant tout rendu.

    Un sous-modèle de plugin ne voit que sa section : il ne peut pas vérifier
    seul ce qui touche au bloc partagé `service:`. Le cœur appelle ce hook juste
    après l'assemblage du modèle ; un `Issue` de niveau `error` arrête la
    génération, un `warning` est affiché et laisse passer.

    Ajouté à la revue d'interface de la phase 4 (arbitrage R2) : sans lui, une
    spécification incohérente était générée sans broncher et l'erreur ne
    sortait qu'au `forge validate` suivant.
    """


@hookspec
def forge_consistency(spec: ForgeSpec, outdirs: dict[str, Path]) -> list[Issue]:
    """Contrôles supplémentaires propres au plugin (échappatoire).

    Seul hook appelé sur **tous** les plugins à la fois ; les résultats sont
    concaténés. À n'utiliser que pour ce que `forge_projection` ne peut pas dire.
    """

@hookspec
def forge_catalog() -> list[CatalogEntry] | None:
    """Catalogue consultable via `forge catalog <domaine>` (facultatif)."""
```

### 2.3 Appel des hooks — point d'attention pluggy

`pm.hook.forge_answers(...)` appelle **tous** les plugins et retourne une liste.
Or forge a besoin d'adresser **un** domaine à la fois. Le cœur encapsule donc
`pm.subset_hook_caller()` dans une façade :

```python
manager.domains()            # -> list[DomainInfo], trié par nom (déterminisme)
manager.domain("ansible")    # -> DomainHooks : .spec_model() .answers(spec) .validators(...) …
```

Aucun `firstresult=True` sur les hooks propres à un domaine : ils seraient
silencieusement captés par le premier plugin enregistré. Seul `forge_consistency`
est consommé en mode « tous les plugins ».

### 2.4 Enregistrement

Phase 2 : les plugins internes (`demo`, puis `ansible`, `helm`) sont enregistrés
en dur dans `forge/plugins_api/manager.py`. La découverte par entry-points
(`pm.load_setuptools_entrypoints("forge")`) est ajoutée plus tard sans changer le
contrat. **Ajouter un domaine ne doit toucher aucun fichier du cœur** hormis cette
liste d'enregistrement.

---

## 3. Format de `forge.yml`

Une section partagée `service:`, une section optionnelle par plugin. Un domaine
absent n'est pas généré.

```yaml
---
forge_version: 1

# ---------------------------------------------------------------------------
# Bloc partagé : ce que tous les domaines doivent voir de la même façon.
# ---------------------------------------------------------------------------
service:
  name: shop                      # DNS label : sert de nom de projet, de chart et de préfixe
  description: "Boutique en ligne"
  owner: "Equipe Plateforme"
  owner_email: "plateforme@example.com"
  labels:                         # labels métier, repris par tous les domaines
    app.kubernetes.io/part-of: commerce
    tier: frontend
  environments:                   # ordre significatif : dev -> staging -> prod
    - name: dev
      domain: dev.example.net     # domaine DNS de l'environnement (facultatif)
    - name: staging
      domain: staging.example.net
    - name: prod
      domain: example.net
      production: true            # active les profils durcis des plugins

# ---------------------------------------------------------------------------
# Domaine Ansible
# ---------------------------------------------------------------------------
ansible:
  os_family: debian               # debian | redhat
  remote_user: ansible
  become: true
  ssh_port: 22
  python_interpreter: auto_silent
  options:
    use_vault: true
    write_lint_config: true
    write_ci: false
  groups:
    - name: webservers
      description: "Serveurs web frontaux"
      roles: [common, users, ssh_hardening, firewall, nginx]
    - name: dbservers
      description: "Serveurs de base de données"
      roles: [common, users, ssh_hardening, firewall, postgresql]
  hosts:                          # par environnement, puis par groupe
    dev:
      webservers:
        - {name: web-dev-01, ansible_host: 192.168.56.11}
      dbservers:
        - {name: db-dev-01, ansible_host: 192.168.56.21}
    prod:
      webservers:
        - {name: web-prod-01, ansible_host: 10.0.1.11}
        - {name: web-prod-02, ansible_host: 10.0.1.12}
      dbservers:
        - {name: db-prod-01, ansible_host: 10.0.2.11}
  roles:                          # options des rôles ; complété par les défauts du catalogue
    - name: nginx
      options:
        nginx_server_name: shop.example.net
        nginx_document_root: /var/www/shop

# ---------------------------------------------------------------------------
# Domaine Helm
# ---------------------------------------------------------------------------
helm:
  kubernetes:
    version: "1.31"
  layout: single                  # single | umbrella
  namespace_strategy: per_env     # single | per_env | custom
  create_namespace: false
  image:
    registry: docker.io
    repository: acme/shop
    strategy: appVersion          # appVersion | per_env | fixed
    pull_policy: IfNotPresent
  components:
    - name: api
      kind: deployment
      addons: [service, ingress, configmap, hpa, pdb, serviceaccount]
      port: 8080
    - name: worker
      kind: deployment
      addons: [configmap]
  secrets:
    strategy: placeholder         # jamais de valeur réelle générée
  extras:
    makefile: true
    helm_tests: true

# ---------------------------------------------------------------------------
# Domaine Terraform (phase 7)
# ---------------------------------------------------------------------------
# Le socle sur lequel les autres domaines se posent : le cloisonnement, son
# budget, l'identité qui y déploie. Pas la charge applicative — c'est Helm.
terraform:
  terraform_version: "~> 1.9"     # contrainte, jamais une version nue
  namespace_strategy: per_env     # same | per_env | custom
  resources:                      # familles retenues ; le reste n'est pas généré
    - namespace
    - quota
    - service_account
  backend:
    kind: s3                      # local | s3 | gcs | azurerm | http
    config:                       # aucune clé secrète : le modèle les refuse
      bucket: etats-terraform
      region: eu-west-3
  kubernetes:
    auth: kubeconfig              # kubeconfig | in_cluster
    context_per_environment: true
  environments:
    prod:
      kube_context: prod-eu-west-3
      quota: { cpu: "16", memory: 32Gi, pods: 120 }
  extras:
    makefile: true
    tflint_config: true
```

```yaml
# ---------------------------------------------------------------------------
# Domaine monitoring (phase 9)
# ---------------------------------------------------------------------------
# Domaine autonome : il ne lit aucune autre section. Ce qu'il surveille est
# déclaré ici, et la cohérence avec les autres domaines passe par les facettes.
monitoring:
  scrape:
    interval: 30s                 # le délai doit rester sous l'intervalle
    timeout: 10s
    metrics_path: /metrics
  metrics:                        # noms propres à la bibliothèque cliente
    requests_total: http_requests_total
    request_duration_seconds: http_request_duration_seconds
    status_label: status
  rules:                          # familles retenues ; le reste n'est pas généré
    - availability
    - error_rate
    - probe
  environments:
    prod:
      namespace: boutique-prod
      targets: ["api-1.example.net:9090"]
      probe_urls: ["https://boutique.example.net"]
      thresholds: { error_rate: 0.02, certificate_days: 30 }
  extras:
    makefile: true
    dashboard: true
```

Une configuration de collecte et un jeu de règles **par environnement** : les
seuils diffèrent, le namespace observé aussi. Chaque règle d'alerte est livrée
avec le test unitaire qui prouve qu'elle se déclenche — ce n'est pas une option.

```yaml
# ---------------------------------------------------------------------------
# Domaine pipeline (phase 8)
# ---------------------------------------------------------------------------
# Le seul domaine dont la sortie dépend des AUTRES sections, et le seul dont la
# sortie est la racine du dépôt : un fichier de CI n'existe que là où son outil
# le lit.
pipeline:
  provider: github              # github | gitlab
  runner: ""                    # vide : défaut propre à l'outil choisi
  trigger:
    branches: [main]
    on_pull_request: true
  build:                        # absent : aucun job de construction
    context: .
    dockerfile: Dockerfile
    registry: ghcr.io
    image: acme/boutique
  deploy:                       # absent : le pipeline se limite à valider
    environments: [dev, prod]   # vide : tous
    manual_for_production: true
    sequential: true
```

Rien ici ne dit **quels domaines valider** ni **quelles commandes lancer** :
ceux-là sont ceux que la spécification demande, et chaque domaine déclare ses
propres commandes (`forge_validators`, `forge_deploy`). Le cœur transmet ces
faits par un `GenerationContext` ; il n'ordonnance rien.

La clé d'état (`key`, `prefix`) n'est **pas** demandée à la spécification : elle
est dérivée par environnement, pour que deux racines n'écrivent jamais le même
état. Le domaine Terraform déclare la facette `namespaces`, la même que Helm :
c'est là que les deux domaines doivent s'accorder, et `forge validate` le
vérifie sans qu'aucune règle « si terraform alors helm » n'existe dans le cœur.

### 3.1 Correspondance avec les specs legacy

| Champ legacy | Origine | Cible dans `forge.yml` |
|---|---|---|
| `project_name` | ansible | `service.name` |
| `description`, `author` | ansible | `service.description`, `service.owner` |
| `environments[].name` | ansible | `service.environments[].name` |
| `environments[].hosts` | ansible | `ansible.hosts.<env>` |
| `environments[].group_vars` | ansible | `ansible.group_vars.<env>` |
| `groups`, `roles`, `options`, `os_family`, `remote_user`, `become`, `ssh_port`, `python_interpreter` | ansible | section `ansible:` à l'identique |
| `spec_version` | ansible | `forge_version` (unifié) |
| `app.name` | helm | `service.name` |
| `app.description`, `app.maintainer_*` | helm | `service.description`, `service.owner`, `service.owner_email` |
| `app.chart_version`, `app.app_version` | helm | `helm.chart_version`, `helm.app_version` |
| `environments[].name` | helm | `service.environments[].name` |
| `environments[].namespace`, `.log_level`, `.components`, `.extra_values` | helm | `helm.environments.<env>` (surcharges) |
| `kubernetes`, `layout`, `namespace_strategy`, `create_namespace`, `image`, `components`, `secrets`, `extras` | helm | section `helm:` à l'identique |
| `schema_version` | helm | `forge_version` (unifié) |

Convertisseur : **non nécessaire en production** (aucun `forge.yml` legacy n'existe
hors des dépôts d'origine), mais un helper **de test** `tests/legacy_spec.py`
convertira les 5 specs ansible et les 2 specs helm pour alimenter les
instantanés de parité des phases 3 et 4.

---

## 4. Arborescence générée (monorepo deux domaines)

```
<cible>/
├── forge.yml                    # copie de la spec (rejouabilité) — écrite par le cœur
├── README.md                    # index des domaines — écrit par le cœur (cf. §8 Q6)
├── .gitattributes               # eol=lf, indispensable aux comparaisons golden
├── ansible/
│   ├── .copier-answers.yml      # _commit, _src_path, plugin, service, domain
│   ├── ansible.cfg
│   ├── requirements.yml
│   ├── inventories/<env>/hosts.yml
│   ├── inventories/<env>/group_vars/{all,<groupe>}.yml
│   ├── inventories/<env>/host_vars/<hôte>.yml
│   ├── group_vars/<groupe>.yml
│   ├── playbooks/{site,ping,<groupe>}.yml
│   └── roles/<rôle>/{tasks,handlers,defaults,vars,meta,templates,README.md}
└── helm/
    ├── .copier-answers.yml
    ├── Makefile
    └── charts/<service>/
        ├── Chart.yaml, values.yaml, values-<env>.yaml, README.md, .helmignore
        └── templates/{_helpers.tpl, NOTES.txt, <composant>-<ressource>.yaml, tests/}
```

Chaque domaine est autonome : son `.copier-answers.yml` permet de le mettre à jour
seul (`forge update --only helm`).

---

## 5. Invocation de copier

### 5.1 `copier.yml` racine (unique, à la racine du dépôt forge)

```yaml
_subdirectory: "[[ template_subdir ]]"     # fourni par le hook forge_template_subdir
_answers_file: .copier-answers.yml
_templates_suffix: .jinja
_jinja_extensions:
  - forge.jinja_ext.ForgeExtension
_envops:
  block_start_string: "[%"
  block_end_string: "%]"
  variable_start_string: "[["
  variable_end_string: "]]"
  comment_start_string: "[#"
  comment_end_string: "#]"
  trim_blocks: true
  lstrip_blocks: true
  keep_trailing_newline: true

# Questions déclarées : SEULES les questions déclarées sont enregistrées dans le
# fichier de réponses, donc seules elles survivent à `copier update`.
plugin:          {type: str}
template_subdir: {type: str}
forge_version:   {type: int, default: 1}
service:         {type: json}
domain:          {type: json}
```

Un seul `copier.yml`, donc des délimiteurs `[[ ]]` **pour tous les plugins** — y
compris Ansible (cf. §8 Q1). Les gabarits accèdent à `[[ service.name ]]`,
`[[ domain.groups ]]`, etc.

Chaque gabarit de plugin contient obligatoirement
`[[ _copier_conf.answers_file ]].jinja` (sinon aucun fichier de réponses n'est
écrit et l'update est impossible).

### 5.2 Génération

```python
run_copy(
    src_path=str(template_root),               # racine du dépôt forge (dépôt git)
    dst_path=str(target / domain.outdir),      # <cible>/ansible
    data={
        "plugin": domain.name,
        "template_subdir": hooks.template_subdir(),
        "forge_version": spec.forge_version,
        "service": spec.service.model_dump(mode="json"),
        "domain": hooks.answers(spec),
    },
    defaults=True,      # obligatoire : sinon prompt interactif -> plantage sous Git Bash
    unsafe=True,        # requis dès qu'on déclare _jinja_extensions
    quiet=True,
    overwrite=force,
    vcs_ref=ref,        # "HEAD" par défaut : inclut les gabarits non committés
)
```

`template_root` est résolu dans cet ordre : `$FORGE_TEMPLATE_SRC`, puis la racine
git contenant `forge/__init__.py`, puis l'URL de publication (usage installé).

Sous Windows, le cœur enveloppe tout appel copier avec
`GIT_CONFIG_COUNT=1 / GIT_CONFIG_KEY_0=core.longpaths / GIT_CONFIG_VALUE_0=true` :
les noms de chemin porteurs de `yield` dépassent sinon la limite dans le clone
temporaire de copier.

### 5.3 Multiplicité des fichiers — la balise `yield`

Le `planner.py` legacy disparaît au profit de chemins de gabarit :

```
inventories/[% yield e from domain.envs %][[ e.name ]][% endyield %]/hosts.yml.jinja
inventories/[% yield e from domain.envs %][[ e.name ]][% endyield %]/host_vars/[% yield h from e.hosts %][[ h.name ]][% endyield %].yml.jinja
roles/[% yield r from domain.roles %][[ r.name ]][% endyield %]/tasks/main.yml.jinja
charts/[[ service.name ]]/values-[% yield e from domain.envs %][[ e.name ]][% endyield %].yaml.jinja
```

Règles (vérifiées) : une seule balise `yield` par **segment** de chemin ;
imbrication possible entre segments, la variable du segment parent restant
disponible ; interdite dans le contenu d'un fichier ; un segment rendu vide
supprime le fichier (`[% if %]` = filtre de fichier).

Conséquence pour les rôles Ansible : les gabarits communs à tous les rôles
(`meta`, `README`) s'écrivent une fois sous un `yield` de rôle ; les fichiers
spécifiques à un rôle (ex. `firewall/tasks/ufw.yml`) sont filtrés par
`[% if r.name == 'firewall' %]`, ou rangés dans un sous-arbre conditionnel.
**Arbitrage à faire en phase 3 sur un rôle réel avant de convertir les 7.**

### 5.4 `forge update`

```python
# 1. réécrire _src_path (absolu, donc lié au poste d'origine) vers template_root
# 2. puis :
run_update(dst_path=str(target / domain.outdir),
           defaults=True, overwrite=True, unsafe=True,
           conflict="inline", vcs_ref=ref)
```

Vérifié : une évolution de gabarit est fusionnée à trois branches dans un fichier
édité à la main, les deux modifications étant conservées. `_commit` passe d'un tag
à l'autre. `--only` restreint aux domaines demandés.

Prérequis : le répertoire cible est un dépôt git (copier l'exige pour la fusion),
et le gabarit doit être **committé** si `--ref` désigne un tag.

### 5.5 `forge diff`

Rendu dans un répertoire temporaire (`run_copy` vers un tmpdir, jamais `pretend`,
qui n'écrit rien), puis comparaison structurelle avec la cible :
fichiers ajoutés / supprimés / modifiés, et nombre de lignes changées. Résumé
seulement — aucun diff intégral affiché (règle d'économie de contexte).

---

## 6. Validation

1. **Validateurs de domaine** : `forge_validators(spec, outdir) -> list[Command]`,
   exécutés par le runner du cœur (subprocess, timeout, capture, chaînage stdin
   via `stdin_from`, rapport `Report`/`Check` repris de helm-forge).
2. **Outil absent** : message d'installation (`install_hint`), pas de trace Python.
   Sortie en échec explicite, ou `SKIP` signalé si `--skip-missing`.
3. **Repli WSL** : sous Windows, une commande `requires_linux=True` est relancée
   via `wsl.exe -d <distro>`, le projet étant recopié hors du montage Windows
   (Ansible refuse un `ansible.cfg` world-writable). Portage direct de
   `tests/ansible_tools.py`.
4. **Contrôles inter-domaines** (cœur, domaine-agnostiques) : comparaison des
   `Projection` — `service_name` identique partout, `environments` identiques,
   `labels` non contradictoires, puis toute `facet` déclarée par au moins deux
   domaines (ex. `hosts` déclaré par ansible et par helm via les hôtes d'Ingress).
5. **Échappatoire** : `forge_consistency` pour ce que les projections ne
   capturent pas.

---

## 7. Surface CLI

| Commande | Rôle |
|---|---|
| `forge new [-o DIR] [--spec-out forge.yml] [--only a,b] [--force] [--dry-run]` | entretien (bloc `service:` par le cœur, puis `forge_interview` par domaine), écriture de `forge.yml`, génération |
| `forge generate [-s forge.yml] [-o DIR] [--only …] [--ref REF] [--force] [--dry-run]` | régénère depuis une spec existante |
| `forge validate [-s forge.yml] [-o DIR] [--only …] [--skip-missing]` | validateurs par domaine + contrôles inter-domaines |
| `forge update [-o DIR] [--only …] [--ref REF] [--conflict inline\|rej]` | `copier update` par domaine |
| `forge diff [-s forge.yml] [-o DIR] [--only …]` | écart entre la cible et un rendu neuf (résumé) |
| `forge plugins` | domaines enregistrés, sections reconnues, état des outils externes |
| `forge catalog <domaine> [élément]` | catalogue fourni par le plugin (rôles, composants) |
| `forge --version` | version |

Conventions communes : `--only` accepte une liste de domaines (erreur explicite
sur un domaine inconnu), `--dry-run` n'écrit rien, sortie non colorée si
`NO_COLOR` est défini.

---

## 8. Questions ouvertes — **arbitrees le 2026-08-23**

> Les huit questions ont ete tranchees. Q1, Q5, Q6 et Q7 par reponse explicite ;
> Q2, Q3, Q4 et Q8 retenues telles que recommandees, sans objection. Cette
> section est desormais un releve de decisions : ne pas la rouvrir sans raison
> nouvelle. Q9 en est une, apparue en production le 2026-09-24 et arbitree le
> jour meme : elle s'ajoute a la suite, elle ne rouvre aucune des huit.

**Q1. Délimiteurs des gabarits Ansible.** Le legacy utilise `{{ }}` plus des
helpers `j()`/`jstr()` et 6 blocs `{% raw %}` pour émettre du Jinja destiné à
Ansible. Un `copier.yml` unique impose un seul jeu de délimiteurs.
→ **DECISION : `[[ ]]` pour tous les plugins.** Les gabarits Ansible
écrivent alors `{{ ma_variable }}` littéralement, `j()`/`jstr()` et les `{% raw %}`
disparaissent. Simplification nette, au prix d'une conversion mécanique des
51 gabarits en phase 3. *(Alternative : un dépôt de gabarit par plugin, donc
plusieurs `copier.yml` — mais alors plus de `_subdirectory` unique et une
mécanique d'update par plugin plus lourde.)*

**Q2. Emplacement du gabarit et `copier update`.** Vérifié : un `src_path`
pointant un sous-répertoire d'un dépôt git n'est pas reconnu comme gabarit
versionné → update impossible.
→ **DECISION : `copier.yml` unique à la racine du dépôt forge, avec
`_subdirectory` fourni en donnée.** Validé de bout en bout (copy + update +
fusion d'une édition manuelle).

**Q3. Forme des données passées à copier.** Trois questions déclarées
(`plugin`, `service`, `domain`, plus `template_subdir` et `forge_version`) plutôt
qu'une question par champ métier.
→ **DECISION : la forme à cinq clés.** Seules les questions déclarées
survivent à l'update ; un dict `domain` unique évite de dupliquer le schéma
pydantic dans `copier.yml`, au prix d'un `.copier-answers.yml` plus verbeux
(lisible, versionné, et c'est précisément ce qu'on veut relire).

**Q4. Contrôles inter-domaines.** Deux options : des règles écrites dans le cœur
(qui deviendrait alors domaine-dépendant), ou des projections déclarées par les
plugins et comparées par le cœur.
→ **DECISION : `forge_projection` + comparaison générique**, avec
`forge_consistency` comme échappatoire. Le cœur reste agnostique, et un troisième
plugin (Terraform…) hérite des contrôles sans toucher au cœur.

**Q5. Convertisseur de specs legacy.** Aucun `forge.yml` legacy n'existe hors des
dépôts d'origine (5 specs ansible + 2 specs helm, toutes dans `tests/`).
→ **DECISION : pas de commande `forge import` livrée.** Confirme : aucun
`forge.yml` legacy n'existe hors des depots d'origine. Un helper de test
(`tests/legacy_spec.py`) convertit les 7 specs pour alimenter les instantanes de
parite des phases 3 et 4.

**Q6. Fichiers de niveau dépôt** (`README.md`, `Makefile`, `.gitignore`,
`.gitattributes` à la racine de la cible). Le legacy helm les génère depuis son
gabarit `project/` ; en monorepo ils n'appartiennent à aucun domaine.
→ **DECISION : le cœur écrit un minimum non-domaine** (`forge.yml`,
`README.md` listant les domaines, `.gitattributes`) ; le `Makefile` helm et le
`.gitignore` Ansible restent **dans leur sous-répertoire de domaine**
(`helm/Makefile`), ce qui garde chaque domaine autonome et supprimable.

> **Conséquences constatées en phase 2** — ces trois fichiers sont les seuls que
> forge écrit sans passer par copier, ce qui est une exception assumée à la règle
> « le rendu passe toujours par copier » :
> - ils ne sont pas suivis par `copier update`, donc `forge update` ne les
>   rafraîchit pas ; c'est `forge generate` qui les remet à jour ;
> - `forge diff` les compare donc **explicitement** (rubrique `(racine)`), pour
>   ne jamais annoncer « à jour » sur ce qu'il n'aurait pas regardé ;
> - `forge.yml` de la cible est la **source de vérité éditée à la main** : quand
>   la spécification lue *est* celle de la cible, elle n'est pas réécrite, sans
>   quoi la resérialisation détruirait les commentaires de l'équipe ;
> - `README.md` et `.gitattributes` obéissent à la même règle que les fichiers de
>   domaine : pas d'écrasement d'un fichier modifié sans `--force` ;
> - l'index liste les domaines **de la spécification**, jamais ceux du dernier
>   `--only` : un `forge generate --only ansible` ne doit pas faire disparaître
>   `helm/` du README d'un projet où la section `helm:` existe toujours.

**Q7. Validation sous Windows.** Constat : ni ansible-core, ni ansible-lint, ni
helm, ni kubeconform ne sont installés côté Windows ; helm 4.2.4 et kubeconform
0.8.0 sont présents dans WSL Debian ; ansible-lint n'est installé nulle part.
→ **DECISION : runner du cœur avec repli WSL** (portage de
`tests/ansible_tools.py`). **`pipx install ansible-core ansible-lint` dans WSL
Debian est a ma charge, au debut de la phase 3** (tache inscrite dans PLAN.md) ;
la CI GitHub (Linux) reste l'autorite.

**Q8. Gestion du dépôt et des versions de gabarit.** `copier update` compare des
références git : par défaut le **dernier tag**. En développement, `--ref HEAD`
inclut les gabarits non committés (vérifié).
→ **DECISION : `--ref HEAD` par défaut** (le rendu suit l'arbre de travail,
les tests golden aussi), tags `vX.Y.Z` posés à chaque phase pour offrir des points
d'update stables aux projets générés.

**Q9. Versions des collections Galaxy du projet généré** — *question ouverte
après coup, arbitrée le 2026-09-24.* `requirements.yml` nommait les collections
sans aucune contrainte : `ansible-galaxy collection install -r requirements.yml`
installait ce que Galaxy servait ce jour-là. La CI de forge a pris la panne en
premier — `community.postgresql` 5.0.0 a supprimé `postgresql_set`, et un commit
vieux de trois semaines est passé au rouge — mais la même exposition était livrée
à chaque projet généré. « Même spécification, même sortie » ne dit rien tant que
la sortie nomme des dépendances sans version.
→ **DECISION : plancher *et* plafond de majeure**, autorisés une seule fois par
collection dans `plugins/ansible/catalog/collections.py`.
- **Par collection, jamais par rôle.** Deux rôles qui dépendent de la même
  collection ne doivent pas pouvoir se contredire ; un `RoleDefinition` ne nomme
  donc qu'un nom de collection. Un rôle qui nomme une collection absente de la
  table casse l'import du plugin, pas le projet de l'utilisateur.
- **Le plafond, et pas seulement le plancher.** Un plancher documente ce dont les
  gabarits ont besoin, mais ne protège de rien : la casse vient toujours d'une
  majeure publiée *après* la génération. *(Alternative écartée : plancher seul,
  moins d'entretien pour forge, mais l'incident se reproduit tel quel chez
  l'utilisateur, ce qui est précisément ce qu'on refuse de livrer.)*
- **Conséquence assumée : forge doit suivre les majeures.** Sans montée de
  version régulière, les projets générés vieillissent. La procédure est celle des
  outils épinglés dans `.github/workflows/ci.yml` : monter la version validée en
  CI, monter `max_major`, corriger les gabarits si la majeure a retiré quelque
  chose, livrer la montée dans son propre commit. Un intervalle reste **élargi
  par l'utilisateur à sa main** : `requirements.yml` est un fichier de son
  projet, et l'en-tête généré le dit.
- **Le plancher n'est jamais deviné.** Quand on sait ce qu'exigent les gabarits,
  il le dit (`community.postgresql >= 3.13.0` pour `postgresql_alter_system`).
  Sinon c'est la version validée en CI, avec la raison écrite dans le fichier
  généré : forge ne prétend pas savoir ce qu'il n'a pas testé, et le plancher se
  descend le jour où quelqu'un vérifie.

> **Reste exposé, hors de cette décision** — cette décision ne porte que sur les
> **collections** nommées par `requirements.yml`. Deux installations d'outils
> restent sans version dans ce que forge génère : `pip install --upgrade
> ansible-core ansible-lint` dans le workflow `.github/workflows/ansible-lint.yml`
> du projet Ansible, et la table `plugins/pipeline/tools.py`, où `ansible-core`,
> `ansible-lint` **et les trois collections** sont encore libres et où la liste
> des collections est recopiée. La première se pin en trois lignes ; la seconde
> demande que `pipeline` apprenne les versions du domaine
> `ansible` sans l'importer — donc une projection, donc une décision à part.

---

## 9. Arborescence du dépôt forge

*Constatée après la phase 10, et non plus prévue.*

```
forge/
├── CLAUDE.md  PLAN.md  MIGRATION.md  DESIGN.md  README.md
├── copier.yml                     # gabarit racine unique (§5.1)
├── partials/header.jinja          # macros partagées par les gabarits
├── pyproject.toml                 # uv, python >=3.11
├── .gitattributes                 # * text=auto eol=lf
├── examples/                      # cinq spécifications, toutes testées
├── src/forge/
│   ├── cli.py  errors.py  jinja_ext.py  pipeline.py
│   ├── spec/         io.py  service.py  assembly.py  names.py  types.py
│   ├── plugins_api/  hookspecs.py  manager.py  types.py  checks.py
│   ├── interview/    prompter.py  service_flow.py
│   ├── render/       copier_runner.py  scaffold.py  diff.py
│   ├── validate/     runner.py  tools.py  wsl.py  consistency.py
│   └── plugins/
│       ├── demo/        plugin.py  template/        # tests du cœur uniquement
│       ├── ansible/     plugin.py  spec.py  catalog/  interview.py  validators.py  template/
│       ├── helm/        plugin.py  spec.py  catalog/  interview.py  validators.py  template/
│       ├── terraform/   plugin.py  spec.py  catalog/  interview.py  validators.py  template/  hcl.py
│       ├── monitoring/  plugin.py  spec.py  catalog/  interview.py  validators.py  template/  render.py
│       └── pipeline/    plugin.py  spec.py  jobs.py  tools.py  interview.py  validators.py  template/
└── tests/
    ├── specs/  golden/
    ├── conftest.py  scripted_prompter.py  isolated_domain.py  fake_domains/
    └── test_*.py
```

### Écarts avec ce que ce document prévoyait

| Ajout | Pourquoi |
| --- | --- |
| `pipeline.py` | pour que `cli.py` ne porte aucune logique : les opérations sont appelables sans terminal |
| `interview/service_flow.py`, `render/scaffold.py`, `render/diff.py` | responsabilité unique, et limite de 600 lignes |
| `plugins_api/checks.py` | quatre domaines réécrivaient le même contrôle « environnement inconnu » ; il ne parle que de `service.environments`, donc il reste agnostique |
| `plugins/terraform/hcl.py` | `terraform fmt` aligne le `=` de lignes consécutives : un gabarit ne peut pas aligner des clés dont il ignore la longueur, la projection si |
| `plugins/monitoring/render.py` | une annotation d'alerte et l'annotation attendue par son test unitaire sont calculées ensemble, sans quoi elles divergent |
| `plugins/pipeline/jobs.py`, `tools.py` | dériver des jobs d'un `GenerationContext`, et savoir installer les outils que les commandes citent — la seule table du projet qui nomme des binaires |
| `partials/` à la racine | macros partagées entre gabarits, résolues par le chargeur Jinja de copier |

`tests/parity/` a existé pendant tout le portage puis a été retiré en phase 10,
avec `_legacy/` (cf. `MIGRATION.md`, section de clôture).

Limite de 600 lignes par fichier (CLAUDE.md global) : le plus gros fichier de
`src/` en compte 420 ; le plus gros module de test, 468.
