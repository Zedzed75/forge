# MIGRATION.md — du legacy vers forge

Source de vérité unique sur le code legacy. À consulter **au lieu** de relire
`_legacy/`, qui sera supprimé en phase 6.

Audit réalisé le 2026-08-23 sur `_legacy/ansible-forge` (HEAD `73c5b26`, 6 commits)
et `_legacy/helm-forge` (HEAD `e5d492c`, 3 commits).

---

## 1. Maturité constatée (vérifiée, pas déclarée)

| | ansible-forge | helm-forge |
|---|---|---|
| Étapes du plan d'origine achevées | 6 / 6 (jusqu'à « revue critique, documentation, démo ») | 3 / ~6 (conception, modèle, moteur + gabarits de base) |
| Génère un projet aujourd'hui ? | **Oui** — `generate --spec examples/forge.yml` produit 96 fichiers | **Oui via l'API** (`render(spec)` + `writer`), **pas de CLI** |
| Suite de tests | **288 tests, verts** (1 skip : ansible-lint absent) | **130 tests, verts** (helm 4.2.4 + kubeconform 0.8.0 présents dans WSL) |
| CLI | `new`, `generate`, `validate`, `catalog`, `check` | **absente** — `pyproject` pointe vers `helm_forge.cli:main` qui n'existe pas → entrée morte |
| Catalogue | 7 rôles complets, gabarits inclus | modèle prévoit 9 addons, **gabarits pour `deployment` + `service` seulement** |
| Délimiteurs Jinja2 | `{{ }}` standard + `{% raw %}` (6 fichiers) + helpers `j()`/`jstr()` pour émettre du Jinja Ansible | **`[[ ]]` / `[% %]` / `[# #]` déjà en place** |
| Références golden | 5 specs → 5 arborescences | 2 specs → 2 arborescences |

**Conséquence de planification** : le portage Ansible (phase 3) est un portage
*à parité* ; le portage Helm (phase 4) est un portage **plus une complétion** du
catalogue de composants (8 des 10 composants demandés restent à écrire).

---

## 2. Contraintes techniques découvertes (spike copier 9.17.2, validé)

Ces points ont été vérifiés expérimentalement, pas supposés. Ils conditionnent le
portage des gabarits.

1. **Multiplicité des fichiers** : la balise `yield` de copier
   (`[% yield e from envs %][[ e.name ]][% endyield %]` dans un *nom de chemin*)
   remplace intégralement les `planner.py` legacy. **Les yields s'imbriquent** :
   un yield sur un nom de répertoire et un autre sur un nom de fichier à
   l'intérieur produisent le produit cartésien, la variable du niveau parent
   restant disponible (`inventories/<env>/host_vars/<host>.yml` généré par un
   seul gabarit). Une seule balise `yield` par *segment* de chemin ; interdite
   dans le *contenu* d'un fichier (`YieldTagInFileError`). Un segment rendu vide
   est ignoré → `[% if %]` sert de filtre de fichier.
2. **Filtres Jinja2 personnalisés** : copier n'accepte pas de filtres passés en
   Python, mais `_jinja_extensions` charge une extension importable. Les filtres
   legacy se portent donc dans `forge.jinja_ext.ForgeExtension`
   (filtres **et** globals fonctionnent, vérifié).
3. **`copier update` exige un gabarit versionné** : si `src_path` désigne un
   sous-répertoire d'un dépôt git, copier ne le voit **pas** comme un gabarit VCS,
   n'écrit pas `_commit`, et l'update échoue (« cannot obtain old template
   references »). Parade validée : `src_path` = **racine du dépôt forge** +
   `_subdirectory: "src/forge/plugins/[[ plugin ]]/template"` dans un `copier.yml`
   racine unique. `_commit` est alors renseigné et `copier update` fusionne à
   trois branches une évolution de gabarit avec une édition manuelle (vérifié).
4. **Fichier de réponses** : copier n'écrit `.copier-answers.yml` que si le
   gabarit contient `[[ _copier_conf.answers_file ]].jinja`. Ce fichier est
   obligatoire dans chaque gabarit de plugin.
5. **Seules les questions déclarées sont enregistrées** dans les réponses, donc
   seules elles survivent à un `update`. Toute donnée passée à copier doit
   correspondre à une question déclarée dans le `copier.yml` racine.
6. **`vcs_ref`** : par défaut copier utilise le **dernier tag** et travaille sur
   un *clone* — les modifications de gabarit non committées sont invisibles.
   Avec `vcs_ref="HEAD"`, copier inclut l'arbre de travail sale
   (`DirtyLocalWarning`) : c'est le mode attendu en développement et pour les
   tests golden.
7. **Windows / chemins longs** : les noms de chemin porteurs d'une balise `yield`
   sont longs ; le clone temporaire de copier n'hérite pas de `core.longpaths` et
   `git add` y échoue (« Filename too long »). Parade validée, **sans toucher à la
   configuration git de l'utilisateur** : forge exporte
   `GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.longpaths GIT_CONFIG_VALUE_0=true`
   autour de ses appels copier. Le dépôt forge lui-même est configuré avec
   `core.longpaths=true`.
8. **`_src_path` est absolu** dans le fichier de réponses : un projet généré serait
   sinon lié au poste qui l'a généré. Le cœur réécrit `_src_path` vers la racine
   de gabarit courante avant tout `update`.
9. **Pas de prompt interactif** : `defaults=True` est obligatoire, sinon copier
   ouvre un prompt et casse sous Git Bash (`NoConsoleScreenBufferError`).
10. **Un rendu fait depuis un arbre de travail sale n'est pas « updatable »**
    (constaté en phase 2). Avec `vcs_ref="HEAD"` et des modifications non
    committées, copier crée un *commit temporaire* dans son clone jetable et
    l'inscrit dans `_commit`. Ce commit n'existe nulle part ensuite :
    `copier update` échoue sur `git checkout <sha>` → « pathspec did not match ».
    Conséquence pratique : `forge generate` marche toujours en développement,
    mais `forge update` exige un gabarit **committé** (d'où les tags `vX.Y.Z`
    de la décision Q8). Le cœur transforme l'échec brut de copier en message
    explicite, et le test d'update est ignoré tant que le dépôt est sale.
11. **`_src_path` ne doit être réécrit que s'il pointe ailleurs** : réécrire une
    valeur équivalente (séparateurs différents) salit le dépôt cible, et copier
    refuse de mettre à jour un dépôt sale.

---

## 3. ansible-forge — classement par artefact

Cible par défaut : `src/forge/plugins/ansible/`. « cœur » = `src/forge/`.

### Modèle et validation

| Artefact | Décision | Cible | Raison |
|---|---|---|---|
| `models/spec.py` (380 l.) | **adapter** | `plugins/ansible/spec.py` | `ProjectSpec` éclaté : `project_name`/`description`/`author`/`environments` montent dans `service:` ; `os_family`, `remote_user`, `become`, `ssh_port`, `python_interpreter`, `groups`, `hosts`, `roles`, `options` forment la section `ansible:`. Validateurs de champs conservés tels quels. |
| `models/enums.py` (`OSFamily`) | **garder** | `plugins/ansible/spec.py` | domaine pur. |
| `validation.py` (regex, `find_duplicates`, `check_host_address`) | **scinder** | cœur `forge/spec/names.py` + regex Ansible dans le plugin | `find_duplicates`/`check_pattern` sont génériques ; `GROUP_NAME_RE`, `RESERVED_GROUP_NAMES` sont Ansible. |
| `errors.py` | **fusionner** | cœur `forge/errors.py` | hiérarchie commune aux deux outils (`ForgeError`, `SpecFileError`, `ToolMissingError`). |
| `spec_io.py` (110 l.) | **adapter** | cœur `forge/spec/io.py` | chargement/écriture YAML déterministe + en-tête commenté : générique. L'en-tête devient paramétrable (liste des sections présentes). |

### Catalogue de rôles

| Artefact | Décision | Cible | Raison |
|---|---|---|---|
| `catalog/definition.py` (`RoleOption`, `RoleDefinition`, `OptionKind`) | **garder** | `plugins/ansible/catalog/definition.py` | vocabulaire Ansible (`collections`, `handlers`, `os_families`) → reste dans le plugin. |
| `catalog/registry.py` (ordre figé, `sort_roles`, `validate_options`) | **garder** | `plugins/ansible/catalog/registry.py` | l'ordre du catalogue conditionne le déterminisme de la sortie. |
| `catalog/roles/{common,users,ssh_hardening,firewall,nginx,docker,postgresql}.py` | **garder** | idem | 7/7 rôles demandés déjà décrits. |

### Moteur (remplacé par copier)

| Artefact | Décision | Cible | Raison |
|---|---|---|---|
| `engine/renderer.py` | **jeter** | — | copier fournit l'environnement Jinja2. La normalisation de sortie (rstrip par ligne, une seule ligne vide finale) est **à reporter** dans le cœur, en post-traitement des fichiers rendus. |
| `engine/planner.py` (382 l.), `engine/role_planner.py` (232 l.) | **jeter → convertir** | arborescence de gabarit + balises `yield` | conversion la plus lourde de la phase 3 : chaque `PlannedFile` devient un chemin de gabarit. |
| `engine/writer.py`, `engine/artifact.py` | **jeter** | — | copier écrit. |
| `engine/filters.py` (148 l.) | **scinder** | cœur `forge/jinja_ext.py` : `comment`, `yaml_scalar`, `yaml_assign`, `lower_first`, `rule` | génériques (mise en forme YAML et commentaires). |
| globals `j()` / `jstr()` | **jeter** | — | ils n'existent que pour émettre du `{{ }}` Ansible depuis un gabarit `{{ }}`. Avec les délimiteurs `[[ ]]`, on écrit `{{ var }}` littéralement. |
| `{% raw %}` (6 gabarits `.j2.j2`) | **jeter** | — | même raison. |

### Interaction et CLI

| Artefact | Décision | Cible | Raison |
|---|---|---|---|
| `prompts/prompter.py` (protocole `Prompter` + `QuestionaryPrompter`) | **garder** | cœur `forge/interview/prompter.py` | abstraction déjà indépendante du domaine, rejouable en test. |
| `prompts/flow.py` (321 l.), `prompts/role_questions.py` (95 l.) | **adapter** | `plugins/ansible/interview.py` | devient l'implémentation du hook `forge_interview`. La partie identité projet / environnements remonte dans l'entretien `service:` du cœur. |
| `cli.py` (221 l.) | **adapter** | cœur `forge/cli.py` | verbes `new`/`generate`/`validate` conservés ; `catalog` devient `forge catalog ansible` ; `check` fusionne dans `validate`. |
| `verify.py` (126 l.) | **adapter** | `plugins/ansible/validators.py` + cœur `forge/validate/runner.py` | la liste de commandes (`--syntax-check` par environnement, `ansible-lint --offline --nocolor`) va au plugin ; l'exécution, le timeout, la détection d'outil manquant et le rapport vont au cœur. |

### Gabarits

| Artefact | Décision | Cible | Raison |
|---|---|---|---|
| `templates/partials/header.j2` (macro `file_header`) | **garder (adapter délimiteurs)** | cœur ou `plugins/ansible/template/` | en-tête commenté obligatoire de chaque fichier généré (règle transverse de CLAUDE.md) → candidat au cœur. |
| `templates/project/*.j2` (17 fichiers) | **adapter** | `plugins/ansible/template/` | conversion `{{ }}` → `[[ ]]`, `{% %}` → `[% %]` ; les chemins paramétrés par environnement / groupe / hôte deviennent des `yield`. |
| `templates/roles/**/*.j2` (33 fichiers) | **adapter** | `plugins/ansible/template/roles/[% yield r from roles %]…` | idem, plus un `yield` par rôle ; les gabarits Ansible d'exécution (`*.j2.j2`) perdent leurs `{% raw %}` et deviennent `*.j2.jinja`. |

### Tests et outillage

| Artefact | Décision | Cible | Raison |
|---|---|---|---|
| `tests/test_golden.py` + option `--regen-golden` | **garder** | cœur `tests/test_golden.py` | harnais exactement adapté au besoin ; comparaison désormais sur l'arborescence écrite par copier. |
| `tests/conftest.py` (`build_spec`) | **adapter** | `tests/conftest.py` | fabrique de spec valide minimale. |
| `tests/ansible_tools.py` (120 l., pont WSL) | **garder → cœur** | `forge/validate/wsl.py` | « exécuter un outil externe nativement ou via WSL, en recopiant le projet hors des montages Windows » est générique et **indispensable** ici : ansible-core ne tourne pas sous Windows. |
| `tests/scripted_prompter.py` | **garder** | `tests/scripted_prompter.py` | rejoue un entretien sans terminal. |
| `tests/test_{models,catalog,engine,cli,flow,role_consistency,spec_io,verify,examples,ansible_validation}.py` | **adapter** | `tests/` | ~1 700 lignes à réaffecter : `test_engine` (rendu) devient golden ; `test_role_consistency` (cohérence catalogue ↔ gabarits) est à conserver tel quel, il attrape les vraies régressions. |
| `.github/workflows/ci.yml` | **adapter** | `.github/workflows/ci.yml` | matrice 3.11/3.12/3.13 + installation d'ansible-core/ansible-lint : **la CI fait autorité** pour la validation Ansible. À étendre à helm + kubeconform. |
| `.gitattributes` (`* text=auto eol=lf`) | **garder** | racine forge | indispensable aux comparaisons golden octet pour octet. |
| `examples/` (spec + projet `plateforme-web`) | **adapter** | `examples/` (phase 6) | devient l'exemple deux domaines. |
| `docs/design.md`, `docs/example-session.md` | **jeter** | — | remplacés par `DESIGN.md` ; contenu utile absorbé ici. |

---

## 4. helm-forge — classement par artefact

Cible par défaut : `src/forge/plugins/helm/`.

| Artefact | Décision | Cible | Raison |
|---|---|---|---|
| `models/spec.py` (312 l.) | **adapter** | `plugins/helm/spec.py` | `app` (nom, description, mainteneur) monte dans `service:` ; `kubernetes`, `layout`, `namespace_strategy`, `image`, `components`, `secrets`, `extras` forment la section `helm:`. **Garder** la dérivation implicite (namespaces, profils par environnement, hôtes d'Ingress) : c'est elle qui rend un `forge.yml` minimal équivalent à un `forge.yml` complet. |
| `models/component.py` (395 l.) | **garder** | `plugins/helm/spec.py` | catalogue de composants sous forme de modèle ; base des 10 composants demandés. |
| `models/enums.py` (122 l.) | **garder** | idem | `ComponentKind`, `AddonKind`, stratégies. `SERVICEMONITOR` est hors périmètre phase 4 : à laisser déclaré mais non généré, ou à retirer. |
| `models/profiles.py` (149 l.) | **garder** | idem | profils dev/staging/prod (replicas, ressources, niveau de log). |
| `models/validators.py` (`DnsLabel`, `Subdomain`, `SemVer`, `ImageRepository`) | **scinder** | `DnsLabel`/`Subdomain`/`SemVer` → cœur `forge/spec/types.py` ; `ImageRepository` → plugin | les trois premiers servent aussi au nom de service partagé. |
| `models/base.py` (`ForgeModel`, `extra="forbid"`) | **jeter** | cœur | doublon exact du `ForgeModel` d'ansible-forge. |
| `constants.py` (94 l.) | **adapter** | `plugins/helm/constants.py` | `KUBERNETES_VERSIONS` à réviser (helm local = 4.2.4). |
| `spec_io.py` (98 l.) | **jeter** | cœur | doublon de celui d'ansible-forge, moins complet. |
| `errors.py` | **fusionner** | cœur | `ToolNotFoundError` ≡ `ToolMissingError`. |
| `engine/environment.py` (délimiteurs `[[ ]]`) | **jeter, valeurs conservées** | `copier.yml` racine, clé `_envops` | le choix de délimiteurs est repris à l'identique — d'où un portage de gabarits sans conversion. |
| `engine/filters.py` (145 l.) | **scinder** | cœur `forge/jinja_ext.py` (`to_yaml`, `yaml_value`, `yaml_scalar`, `comment`, `indent_block`) + `camel` côté plugin | doublons partiels avec les filtres Ansible : **fusionner en une seule implémentation** (attention : `comment` et `yaml_scalar` existent en deux versions divergentes — arbitrer en phase 4 et régénérer les golden). |
| `engine/naming.py` (`helper_name`, `values_ref`) | **garder** | `plugins/helm/jinja_ext.py` | exposé aux gabarits via une extension Jinja de plugin. |
| `engine/planner.py` (186 l.) | **jeter → convertir** | arborescence + `yield` | un `yield` par composant, un par environnement (`values-<env>.yaml`). |
| `engine/renderer.py`, `engine/writer.py` | **jeter** | — | copier. |
| `validation/tools.py` (72 l.) | **fusionner** | cœur `forge/validate/tools.py` | détection PATH, versions, messages d'installation ; identique en intention au `verify.py` Ansible. |
| `validation/runner.py` (144 l.) | **scinder** | commandes → `plugins/helm/validators.py` ; exécution et rapport → cœur | `helm lint`, `helm template` par environnement, `kubeconform -strict` avec la version K8s de la spec, **rendu passé par stdin** → le contrat `Command` du cœur doit gérer stdin. |
| `templates/chart/*.j2` (10 fichiers) | **garder** | `plugins/helm/template/` | délimiteurs déjà conformes ; renommage `.j2` → `.jinja`, chemins paramétrés → `yield`. |
| `templates/project/{Makefile,README.md,gitignore}.j2` | **adapter** | à arbitrer (cf. `DESIGN.md` §8 Q6) | fichiers de niveau dépôt, pas de niveau domaine. |
| `tests/{test_models,test_planner,test_render,test_spec_io,test_golden,test_helm}.py` (1 208 l.) | **adapter** | `tests/` | `test_helm.py` (marqueur `integration`, skip si binaire absent) est le modèle à généraliser. |
| `tests/conftest.py` (109 l.) | **adapter** | `tests/conftest.py` | à fusionner avec celui d'ansible-forge. |
| `docs/DESIGN.md` (§1.1–1.10 : questionnaire complet) | **garder comme référence** | absorbé par `plugins/helm/interview.py` en phase 4 | catalogue de questions déjà rédigé, à ne pas réinventer. |
| `pyproject.toml`, entrée `helm-forge = helm_forge.cli:main` | **jeter** | — | pointe vers un module inexistant. |

### Arbitrages du portage Helm (phase 4, 2026-08-25)

L'audit de phase 1 disait « portage plus complétion » ; la mesure le confirme et
le précise : **le modèle legacy est très en avance sur ses gabarits.**
`models/component.py` déclare 9 addons et 12 sous-blocs, mais `templates/chart/`
n'en rend que deux — `deployment` et `service`. Les 32 fichiers de l'instantané
de parité ne couvrent donc qu'une fraction du modèle.

**Conséquence sur la nature de la phase 4** : ce n'est pas un portage à parité
comme la phase 3. C'est un **portage du modèle** (fidèle et vérifiable, parité
définie sur les 32 fichiers de l'instantané) **plus la création de neuf familles
de gabarits** qui n'ont jamais existé. Ces neuf-là ne peuvent pas être prouvées
par la parité : elles le sont par `helm lint`, `helm template` et
`kubeconform -strict`, et par des références golden neuves.

Décisions prises, à ne pas rouvrir sans raison nouvelle :

| # | Point | Décision |
|---|---|---|
| H1 | **Double source pour l'hôte d'Ingress** : le cœur apporte `service.environments[].domain`, le legacy dérive l'hôte de `components[].ingress.base_domain` + `host_includes_env` | `service.environments[].domain` **l'emporte** quand il est renseigné : l'hôte devient `<préfixe>.<domaine-de-l-env>`, **sans** réinsérer le nom d'environnement (le domaine le porte déjà). Repli sur `base_domain` sinon. Aucune des deux specs de l'instantané n'a de `domain` : la parité est préservée, et le champ du cœur prend enfin un sens. |
| H2 | **Double source pour « cet environnement est la production »** : `service.environments[].production` (booléen explicite) vs reconnaissance par le NOM (`prod`, `prd`, `production`…) | `production: true` **force** le profil prod (et `host_includes_env=false`). En son absence, la reconnaissance par nom s'applique — c'est elle qui rend une spec minimale équivalente à une spec complète, et MIGRATION §4 demande de la garder. Un `Issue` de niveau **warning** est émis quand les deux sources divergent, plutôt que de trancher en silence. |
| H3 | `layout: umbrella` déclaré dans l'enum mais `NotImplementedError` dans le planner, aucun gabarit | **Retiré de l'enum.** Laisser une valeur non implémentée dans un schéma `extra="forbid"` est un piège pour l'utilisateur : il l'écrit, elle passe la validation, et la génération explose. À réintroduire avec ses gabarits. |
| H4 | `helm.environments` : liste d'objets portant leur `name` (legacy) ou dict clé par nom (DESIGN §3.1) | **Dict**, comme `ansible.hosts.<env>` et `ansible.group_vars.<env>`. Le nom et l'ordre vivent désormais dans `service.environments`. Conséquence : le contrôle croisé « clé d'environnement inconnue » devient indispensable, exactement comme dans `ansible/answers.cross_check`. |
| H5 | `components[].port` (DESIGN §3) contre `container_port` / `port_name` / `service.port` (legacy) | **Les trois champs legacy sont conservés.** Les fusionner perdrait le cas nominal Helm (Service:80 → conteneur:8080) et le nom de port que reprennent les sondes. `port` serait un faux ami : DESIGN §3 est corrigé. |
| H6 | Plafonds de longueur (`service.name` ≤ 40, nom d'environnement ≤ 20, `description` ≤ 200) et format d'`owner_email` | Vérifiés par le **contrôle croisé du plugin Helm**, jamais par le cœur : ce sont des contraintes de `Chart.yaml` et du budget de 63 caractères des noms de ressources Kubernetes. Le cœur n'a pas à connaître Helm. |
| H7 | Champs morts du legacy (modélisés, jamais lus par un gabarit) | **Gardés** ceux dont le gabarit arrive en phase 4 : `create_namespace`, `secrets.*`, `persistence`, `hpa`, `pdb`, `config`, `secret`, `cron`, `networkpolicy`, `serviceaccount`, `ingress`. **Abandonnés** : `extras.helmfile` et `extras.ci` (aucun gabarit prévu, et la CI est de niveau dépôt — décision Q6), `servicemonitor` (hors périmètre, MIGRATION §4). `extra="forbid"` les refusera proprement. |
| H8 | `extras.ci` (enum `none\|github\|gitlab`) contre `ansible.options.write_ci` (booléen) | Deux domaines exprimaient la même chose de deux façons. **Non porté.** Si une CI Helm devient nécessaire, elle s'alignera sur la forme booléenne, ou remontera au bloc partagé. |
| H9 | `.gitignore` de niveau projet du legacy Helm (il ignore `secrets.yaml`) | Devient `helm/.gitignore`, comme le `.gitignore` d'Ansible : chaque domaine reste autonome et supprimable (décision Q6). |
| H10 | Sentinelle `@spec` : le planner écrivait une copie de la spécification dans le projet | **Supprimée.** La spécification unifiée est écrite par le cœur à la racine de la cible (écart de parité 3). |
| H11 | `validate_assignment=True` du `ForgeModel` legacy, contourné par des écritures dans `__dict__` | **Non réintroduit.** Les dérivations sont calculées dans un `derive.py` pur qui produit directement le dict `domain`, la spec pydantic restant immuable après validation — seul mode compatible avec `.copier-answers.yml`. |
| H12 | Fenêtre `KUBERNETES_VERSIONS` (1.34, 1.35, 1.36) contre l'exemple `1.31` de DESIGN §3 | La fenêtre du modèle fait foi ; **l'exemple de DESIGN §3 est corrigé**. Elle est revalidée contre le `kubeconform` réellement installé, et non élargie pour faire passer un exemple. |

Pièges de conversion mesurés, propres à Helm :

- `comment` n'est appelé par **aucun** gabarit Helm existant : le piège de
  signature signalé en §5 ne concerne pas le portage. En revanche tout **nouvel**
  appel écrit pendant la complétion du catalogue doit nommer la largeur
  (`| comment(width=76)`), sans quoi 76 serait lu comme une indentation.
- `yaml_value(4)` et consorts sont positionnels dans les gabarits legacy, mais
  les deux implémentations ont la **même** signature : rien à renommer. Le filtre
  produit lui-même son séparateur, d'où la balise collée au deux-points — ne pas
  ajouter d'espace en portant, cela créerait un blanc de fin de ligne que le cœur
  ne nettoie plus (écart 10).
- `values.yaml.j2` et `values-env.yaml.j2` sont denses en blocs `[% if %]` et en
  boucles à lignes vides intercalaires. Le moteur legacy écrasait les lignes
  vides multiples après rendu ; le cœur ne le fait plus. **La correction est dans
  le gabarit**, jamais dans le cœur.
- `values_ref(name)` (de `engine/naming.py`) est indispensable : il rend
  `.Values.api` pour un nom compatible Go, et `(index .Values "mon-api")` pour un
  nom à tiret. Sans lui, un composant nommé avec un tiret produit un chart qui ne
  compile pas. À exposer via `forge.plugins.helm.jinja_ext.GLOBALS`.

---

## 5. Doublons à fusionner (dette évitée)

Les deux outils ont réimplémenté la même chose ; une seule version doit survivre,
dans le cœur. **Fusion réalisée en phase 2** — la colonne « où » indique le
fichier qui fait désormais foi.

| # | Doublon | Arbitrage | Où |
|---|---|---|---|
| 1 | `ForgeModel` (`extra="forbid"`) | implémentations identiques, une seule conservée | `forge/spec/types.py` |
| 2 | `spec_io` (YAML déterministe) | version ansible-forge (plus complète), rendue domaine-agnostique ; l'en-tête liste maintenant les domaines présents | `forge/spec/io.py` |
| 3 | Détection d'outil et message d'installation | fusion `verify.require_tools` + `validation.tools.require`, plus repli WSL | `forge/validate/tools.py` |
| 4 | Rapport d'exécution | `Report`/`Check` (helm) conservé, enrichi des états `missing`, `skipped`, `timeout` et du chaînage `stdin_from` | `forge/validate/runner.py` |
| 5 | Filtres `comment`, `yaml_scalar` | **arbitré** : `yaml_scalar` = version ansible-forge (accepte tout scalaire, rendu identique sur les chaînes) ; `comment` = version ansible-forge (préserve l'indentation source, rend les lignes vides en `#`) + paramètre `prefix` de helm-forge. Signature `comment(text, indent=0, width=88, prefix="# ")` : **les gabarits helm qui passaient la largeur en 2ᵉ position doivent la nommer** (`\| comment(width=76)`) — à appliquer en phase 4. | `forge/jinja_ext.py` |
| 6 | Normalisation de sortie | **union rejetée après vérification** : le cœur se limite à CRLF → LF et à un unique saut final ; `.copier-answers.yml` est épargné (écriture interne de copier). Voir l'encadré ci-dessous. | `forge/render/copier_runner.normalise_text` |

> **Pourquoi l'« union » des deux normalisations legacy a été abandonnée.**
> Le plan de migration prévoyait de cumuler le `rstrip` par ligne d'ansible-forge
> et l'écrasement des lignes vides multiples de helm-forge. Mesuré en phase 2 :
> ces deux transformations **ne sont pas neutres**. Dans un scalaire YAML quoté
> sur plusieurs lignes, une ligne vide encode un saut de ligne littéral — les
> écraser change la valeur relue (`'para1\n\npara2'` devient `'para1\npara2'`).
> Dans un bloc `|`, les espaces de fin de ligne font partie de la donnée.
> Appliquées à l'aveugle après le rendu, elles modifiaient donc le contenu livré
> sans le dire, et les références golden — bénies *après* normalisation —
> entérinaient la corruption au lieu de la détecter.
> Le nettoyage des blancs laissés par les blocs `[% if %]` relève du gabarit
> (`trim_blocks` / `lstrip_blocks`, actifs dans le `copier.yml` racine) : vérifié,
> la sortie du plugin `demo` ne contient ni espace de fin ni ligne vide en trop
> sans aucun post-traitement. Le cœur, lui, ne peut pas savoir ce qui porte du
> sens dans un fichier — c'est exactement le genre de connaissance qu'il n'a pas
> le droit d'avoir. **Conséquence pour les phases 3 et 4 :** si un gabarit porté
> laisse des blancs, la correction est dans le gabarit, jamais dans le cœur.

Filtres également réunis dans `forge/jinja_ext.py` sans divergence :
`yaml_assign`, `lower_first`, `rule` (ansible-forge) et `to_yaml`, `yaml_value`,
`indent_block` (helm-forge). `camel` reste au plugin Helm ; `j()`/`jstr()` sont
supprimés (décision Q1). Un plugin ajoute ses propres filtres via un module
`<paquet-du-plugin>.jinja_ext` exposant `FILTERS`/`GLOBALS`, chargé par
`ForgeExtension` : **le copier.yml racine n'est jamais édité pour un domaine**.

---

## 6. Prérequis d'outillage (état vérifié du poste, 2026-08-23)

| Outil | Windows | WSL Debian | Conséquence |
|---|---|---|---|
| python | 3.13.6 | 3.13.5 | ok (cible 3.11+) |
| uv | **absent** | **absent** | à installer (phase 2 : scaffolding uv) |
| git | 2.55.0 | — | ok ; `core.longpaths=true` positionné sur le dépôt forge |
| helm | absent | **4.2.4** | validation Helm depuis WSL |
| kubeconform | absent | **0.8.0** | validation Helm depuis WSL |
| ansible-playbook / ansible-lint | absent | **absent** | **à installer en WSL** (`pipx install ansible-core ansible-lint`) ; sinon la phase 3 ne peut pas valider localement et seule la CI fait foi |
| venv legacy | `ansible-forge/.venv` (Windows) | `~/.venvs/helm-forge` | utilisables pour les instantanés de parité |

---

## 7. Instantanés de parité (phases 3 et 4)

- **Ansible** : `ansible-forge generate --spec examples/forge.yml` fonctionne
  (96 fichiers). Cible : `tests/parity/ansible/`. Les 5 specs de `tests/specs/`
  et leurs golden constituent un second jeu de comparaison.
- **Helm** : pas de CLI, mais `render(spec)` et les 2 golden (`minimal`, `multi`)
  fournissent l'instantané sans exécuter d'outil. Cible : `tests/parity/helm/`.

### Écarts de parité déjà anticipés (à confirmer et compléter)

| # | Écart | Domaine | Raison |
|---|---|---|---|
| 1 | Ajout de `.copier-answers.yml` dans chaque sous-répertoire de domaine | les deux | exigé par `copier update`. |
| 2 | Sortie déplacée sous `ansible/` et `helm/` au lieu de la racine | les deux | monorepo multi-domaines. |
| 3 | `forge.yml` unifié à la racine, remplaçant les deux specs embarquées | les deux | une seule spécification. |
| 4 | Disparition des artefacts produits par `j()` / `jstr()` **si** le rendu diffère d'un caractère | ansible | à vérifier gabarit par gabarit ; l'objectif est zéro différence. |
| 5 | Fichiers de niveau dépôt (`Makefile`, `README.md`, `.gitignore`) déplacés ou fusionnés | les deux | cf. `DESIGN.md` §8 Q6. |
| 6 | Filtres fusionnés (`comment`, `yaml_scalar`) pouvant changer la mise en forme | les deux | arbitrage §5.5 ; toute différence doit être inscrite ici. |
| 7 | Bandeau d'en-tête : « généré par ansible-forge à partir de forge.yml » devient « généré par forge… » | ansible | l'outil a changé de nom ; laisser l'ancien serait faux. La substitution est appliquée au contenu **attendu** par `tests/test_parite_ansible.py`, sinon ce seul mot ferait échouer 20 fichiers sur 24 et noierait les vraies régressions. |
| 8 | `project_name` legacy acceptait le souligné (`^[a-z][a-z0-9_-]{1,62}$`) ; `service.name` est un **label DNS** (pas de souligné) | ansible | le nom du service est partagé par tous les domaines, et Kubernetes impose le label DNS. Aucune des 6 spécifications de l'instantané n'est concernée. |
| 9 | L'option `embed_spec` disparaît : le domaine ne génère plus `forge.yml` | ansible | la spécification unifiée est écrite par le cœur à la racine de la cible (écart 3). |
| 10 | Le cœur ne « nettoie » plus la sortie : plus de `rstrip` par ligne ni de suppression des lignes vides de tête | les deux | ces transformations ne sont pas neutres (§5, encadré). **Conséquence directe pour le portage** : un gabarit qui laissait des blancs comptait sur le nettoyage du moteur legacy ; il doit désormais produire une sortie propre par lui-même, sinon la parité échoue sur ce fichier. |
| 11 | `.copier-answers.yml` est ajouté à `exclude_paths` du `.ansible-lint` généré | ansible | ce fichier n'existait pas dans le legacy ; sa mise en forme est celle de copier et il faisait échouer `ansible-lint` sur **255 violations** de style YAML, alors que le projet Ansible lui-même est propre. Sans cette exclusion, la règle dure « le projet généré passe ses validateurs » était intenable. |
| 12 | Le `README.md` généré annonce toujours `ansible/forge.yml`, qui n'est plus produit (écart 9) | ansible | l'arborescence ASCII du README est figée sur celle du legacy pour rester identique octet pour octet. Le README porte encore d'autres mentions legacy (`ansible-forge generate`) : **à corriger d'un bloc**, en même temps, plutôt qu'au coup par coup. |

### État du portage Ansible (phase 3, 2026-08-25)

**Parité atteinte : 313 fichiers identiques octet pour octet** sur les six cas de
`tests/parity/ansible/`, aux douze écarts ci-dessus près. Le portage est donc
fidèle, et `_legacy/ansible-forge` n'a plus à être relu.

Ce que la parité ne couvrait pas, et qui est couvert autrement :

- **`write_ci: true`** n'apparaît dans aucune spécification legacy : le workflow
  d'intégration continue généré n'existait dans aucun instantané. Il est
  désormais couvert par la spécification golden `tests/specs/ansible-ci.yml`.
- **Les validateurs n'avaient jamais tourné** : la suite legacy annonçait
  « 288 tests verts (1 skip : ansible-lint absent) » — le skip portait
  précisément sur la règle dure de CLAUDE.md. Le projet généré passe maintenant
  `ansible-playbook --syntax-check` sur chaque environnement **et** `ansible-lint`
  en profil `production`, vérifié par un test d'intégration.

Extension du contrat de plugin découverte à l'usage : `Command` porte désormais
un champ `env`. `ANSIBLE_COLLECTIONS_PATH` ne se transmet que par
l'environnement, et sans lui `--syntax-check` échoue sur des modules que
`requirements.yml` déclare pourtant. À reprendre à la revue d'interface de la
phase 4 : `DESIGN.md` §2.1 décrivait `Command` sans ce champ.

| 13 | `charts/<chart>/README.md` annonce encore `helm-forge generate --spec forge.yml` (forme courte) | helm | la substitution de l'écart 7 ne couvre que la forme longue ; la parité octet impose de conserver le nom legacy. Jumeau Helm de l'écart 12. |
| 14 | Le `README.md` de projet Helm écrit `forge generate --force`, drapeau qui ne correspond à aucune option de la CLI | helm | résultat mécanique de la substitution appliquée au contenu attendu. Même famille que 12 et 13. |
| 15 | L'arborescence ASCII du `README.md` de projet Helm liste toujours `forge.yml` sous `helm/` | helm | la spécification est remontée à la racine (écart 3), mais l'arborescence est figée pour la parité. |
| 16 | Le `.gitignore` de niveau projet devient `helm/.gitignore` | helm | décision H9 : chaque domaine reste autonome et supprimable (Q6). |

> **Les écarts 12 à 15 forment un seul lot.** Ce sont tous des mentions périmées
> de l'outil d'origine dans les README générés, maintenues par la contrainte de
> parité. Les corriger un par un casse la parité à chaque fois ; il faut les
> lever **d'un bloc**, en re-bénissant l'instantané dans le même commit, quand
> la parité aura fini de servir — c'est-à-dire au plus tard en phase 6, avec la
> suppression de `_legacy/`.

### État du portage Helm (phase 4, 2026-08-25)

**Parité atteinte : 32 fichiers identiques octet pour octet** sur les deux cas
de `tests/parity/helm/`, aux écarts ci-dessus près.

**Et complétion : neuf familles de ressources créées** — ingress, configmap,
statefulset, cronjob, secret, hpa, pdb, serviceaccount + RBAC, networkpolicy.
Le modèle legacy les déclarait toutes ; aucune n'avait de gabarit.

Le point de méthode qui a rendu la chose vérifiable : les deux spécifications
de parité déclarent `addons: [service]` et `addons: []`, donc **aucun** des neuf
addons. La complétion a donc été écrite pour leur être **totalement inerte** —
chaque bloc n'est rendu que si son addon est présent. La parité n'a pas eu à
être dégradée pour laisser place au neuf : elle est restée à 32/32 pendant tout
le chantier, et les neuf familles sont prouvées séparément par
`tests/golden/helm-complet/`, par `helm lint`, `helm template` et
`kubeconform -strict`.

Cinq défauts trouvés **par la complétion elle-même**, corrigés :

1. **Un StatefulSet sans son Service headless.** Le modèle forçait
   `service.headless = true` mais pas l'addon : le Service n'était donc pas
   généré, et `serviceName` désignait une ressource inexistante — le
   StatefulSet perdait l'identité réseau stable qui est sa seule raison d'être.
   Aucun validateur ne pouvait le voir, le manifeste restant valide.
2. **`rbac.create` et `rbac.rules` écrits en dur dans `values.yaml`**, donc
   inatteignables depuis `forge.yml` et perdus à chaque régénération. Un bloc
   `rbac` a été ajouté au modèle de composant, avec validation des règles
   (l'API refuse une règle sans `verbs` ; `kubeconform` la laisse passer).
3. **`port_name` sans contrainte.** Kubernetes impose le format IANA_SVC_NAME
   (15 caractères) ; un nom de 29 caractères passe `helm lint`, `helm template`
   **et** `kubeconform -strict`, et n'est refusé qu'à l'application.
4. **Un HorizontalPodAutoscaler sans aucune métrique** était généré quand
   aucune réservation de ressources n'était déclarée. Valide au schéma, il
   n'aurait jamais agi — un autoscaler muet est plus trompeur que pas
   d'autoscaler.
5. **`helm.environments.<env>.extra_values` n'était rendu nulle part** : les
   valeurs libres de l'utilisateur disparaissaient en silence. Manque hérité du
   legacy, corrigé ici.

*(À compléter au fil des phases 3 et 4 : toute différence volontaire avec
l'instantané de parité s'inscrit dans ce tableau.)*


---

## Cloture du portage (phase 10, 2026-08-26)

**`_legacy/` est supprime**, avec `tests/parity/`, ses deux modules de test et
son harnais. Ce document est ce qui reste des outils d'origine.

### Les ecarts 12 a 15 sont leves

Ils formaient un seul lot — des mentions perimees de `ansible-forge` et
`helm-forge` dans les README generes, maintenues par la seule contrainte de
parite. Ils ont ete corriges **d'un bloc**, et l'instantane golden re-beni dans
le meme commit, comme prevu :

| Ecart | Etait | Est |
| --- | --- | --- |
| 12 | `ansible-forge generate --spec forge.yml [--output . --force]` | `forge generate --only ansible [--force]`, et le renvoi vers `forge update --only ansible` qui ne perd pas les modifications |
| 13 | `helm-forge generate --spec forge.yml` | `forge generate --only helm`, meme renvoi |
| 14 | `forge generate --force` presente comme un drapeau inexistant | le drapeau **existe** ; l'ecart etait perime, la commande est desormais `forge generate --only helm --force` |
| 15 | l'arborescence du README Helm listait `forge.yml` sous `helm/` | l'arborescence ne montre que `helm/`, et une phrase dit ou vit reellement la specification |

**Deux mentions sont conservees, et ce n'est pas un oubli** :
`ssh_hardening_dropin_file: 99-ansible-forge.conf` et
`users_sudoers_file: 90-ansible-forge`. Ce ne sont pas des mentions
documentaires mais des **noms de fichiers deposes sur les machines gerees**. Les
renommer laisserait l'ancien fichier en place sur tout hote deja gere : deux
drop-in SSH contradictoires, ou deux fichiers sudoers, sans que rien ne le
signale. Le gabarit porte desormais cette explication en commentaire, a
l'endroit ou la question se pose.

### Pourquoi la parite s'arrete

Elle mesurait une ressemblance a des outils qui n'existent plus, et le projet
genere l'avait depassee des la phase 4 :

- le chart Helm compte **neuf familles de ressources** que l'outil d'origine
  n'a jamais eues — son modele les declarait, aucun gabarit ne les rendait ;
- le projet Ansible passe **`ansible-lint` en profil production**, ce que la
  suite d'origine n'avait jamais verifie : son unique test la-dessus etait
  ignore.

La non-regression est desormais tenue par `tests/golden/` seul, qui compare
octet pour octet, et par les validateurs reels de chaque domaine.

### Ce que le portage a laisse au projet

Le patron employe deux fois — **figer un instantane, convertir, boucler jusqu'a
zero ecart** — n'a pas servi aux deux domaines ecrits de zero, qui n'avaient
aucun instantane. Ce sont les validateurs reels qui y ont tenu ce role, et ils
ont trouve ce qu'aucune parite n'aurait vu : `tflint` a signale une variable
declaree et jamais employee, `promtool` a montre que des series de test figees ne
prouvaient rien des que le seuil changeait.
