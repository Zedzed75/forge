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
| 6 | Normalisation de sortie | **union** appliquée : CRLF → LF, rstrip par ligne, runs de lignes vides ramenés à une seule, exactement un saut final ; `.copier-answers.yml` épargné (écriture interne de copier) | `forge/render/copier_runner.normalise_text` |

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

*(À compléter au fil des phases 3 et 4 : toute différence volontaire avec
l'instantané de parité s'inscrit dans ce tableau.)*
