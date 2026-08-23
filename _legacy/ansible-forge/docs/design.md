# ansible-forge — Design (Étape 1, en attente de validation)

## 1. Questions posées par le CLI

### 1.1 Identité du projet
| Clé | Question | Défaut | Validation |
|---|---|---|---|
| `project_name` | Nom du projet | nom du dossier courant | `^[a-z][a-z0-9_-]{1,62}$` |
| `description` | Description courte | `""` | ≤ 200 car. |
| `author` | Auteur / équipe | `git config user.name` sinon `""` | libre |
| `output_dir` | Dossier de sortie | `./<project_name>` | doit être vide ou `--force` |

### 1.2 Cible et connexion
| Clé | Question | Défaut | Validation |
|---|---|---|---|
| `os_family` | Famille d'OS cible | `debian` | `debian` \| `redhat` |
| `remote_user` | Utilisateur SSH | `ansible` | `^[a-z_][a-z0-9_-]{0,31}$` |
| `become` | Escalade de privilèges (sudo) | `true` | bool |
| `ssh_port` | Port SSH | `22` | 1–65535 |
| `python_interpreter` | Interpréteur Python distant | `auto_silent` | chemin absolu ou `auto_silent` |

### 1.3 Environnements
| Clé | Question | Défaut | Validation |
|---|---|---|---|
| `environments` | Environnements (multi-choix + ajout libre) | `dev`, `staging`, `prod` | ≥ 1, `^[a-z][a-z0-9_]*$`, uniques |

### 1.4 Groupes d'hôtes (définis globalement, peuplés par environnement)
| Clé | Question | Défaut | Validation |
|---|---|---|---|
| `groups[].name` | Nom du groupe | `webservers` | `^[a-z_][a-z0-9_]*$` (pas de tiret : contrainte Ansible), unique, ≠ `all`/`ungrouped` |
| `groups[].description` | Rôle métier du groupe | `""` | libre |
| `groups[].roles` | Rôles appliqués à ce groupe (multi-choix dans le catalogue) | `common` | ⊂ catalogue |

### 1.5 Hôtes — boucle `pour chaque environnement × pour chaque groupe`
| Clé | Question | Défaut | Validation |
|---|---|---|---|
| `hosts[].name` | Nom d'inventaire | `<group>-<env>-01` | `^[a-z0-9][a-z0-9._-]{0,62}$`, unique dans l'env |
| `hosts[].ansible_host` | IP ou FQDN | `""` | `ipaddress` OU FQDN valide |
| `hosts[].ansible_port` | Port SSH (si ≠ global) | hérité | 1–65535 |
| `hosts[].ansible_user` | Utilisateur (si ≠ global) | hérité | idem `remote_user` |
| `hosts[].vars` | Variables spécifiques → `host_vars/` | `{}` | clés `^[a-z_][a-z0-9_]*$` |

### 1.6 Questions par rôle (posées seulement si le rôle est sélectionné)
- **common** : timezone (`Europe/Paris`), paquets de base (défaut `curl,vim,htop,ca-certificates`), NTP (`true`), MOTD généré (`true`).
- **users** : liste d'utilisateurs → `name`, `groups`, `sudo` (bool), `ssh_public_key`, `shell` (`/bin/bash`), `state` (`present`).
- **ssh_hardening** : `permit_root_login` (`prohibit-password`), `password_authentication` (`false`), `x11_forwarding` (`false`), `max_auth_tries` (`3`), port (hérité).
- **firewall** : backend (`auto` → ufw sur Debian / firewalld sur RedHat), politique par défaut (`deny`), ports TCP (`22,80,443`), ports UDP (vide).
- **nginx** : `server_name` (`example.local`), `document_root` (`/var/www/<server_name>`), HTTPS (`false`), suppression du site par défaut (`true`), `worker_processes` (`auto`).
- **docker** : canal (`stable`), plugin compose (`true`), utilisateurs du groupe docker (défaut = utilisateurs sudo de `users`), `daemon_options` (json-file + rotation).
- **postgresql** : version (`16`), `listen_addresses` (`localhost`), bases (`name`, `owner`, `encoding`), utilisateurs (`name`, `password_var`, `privs`), entrées `pg_hba`.

### 1.7 Options de génération
| Clé | Question | Défaut |
|---|---|---|
| `use_vault` | Générer les fichiers vault (modèles en clair + doc) | `true` |
| `write_lint_config` | Générer `.yamllint` / `.ansible-lint` / `.gitignore` | `true` |
| `embed_spec` | Copier `forge.yml` dans le projet généré | `true` |
| `write_ci` | Générer un workflow CI de lint | `false` |

---

## 2. Arborescence générée

```
<project_name>/
├── ansible.cfg                     # Config Ansible : inventaire par défaut, roles_path, ssh, callbacks
├── requirements.yml                # Collections Galaxy requises (déduites des rôles choisis)
├── forge.yml                       # Spec ayant produit ce projet (rejouabilité)
├── README.md                       # Prérequis, commandes, inventaires, précédence des variables
├── .gitignore                      # *.retry, .vault_pass, __pycache__, .venv
├── .yamllint                       # Règles YAML alignées sur ansible-lint
├── .ansible-lint                   # Profil de lint + exclusions
│
├── inventories/
│   ├── dev/
│   │   ├── hosts.yml               # Inventaire YAML : groupes + hôtes + ansible_host
│   │   ├── group_vars/
│   │   │   ├── all.yml             # Surcharges de l'environnement dev (toutes machines)
│   │   │   ├── webservers.yml      # Surcharges dev du groupe webservers
│   │   │   └── vault.yml.example   # Secrets (modèle en clair, à chiffrer)
│   │   └── host_vars/
│   │       └── web-dev-01.yml      # Variables propres à cet hôte
│   ├── staging/…                   # même structure
│   └── prod/…                      # même structure
│
├── group_vars/
│   ├── all.yml                     # Défauts projet, tous environnements (précédence la plus basse)
│   └── <group>.yml                 # Défauts projet du groupe (rôles activés, variables métier)
│
├── playbooks/
│   ├── site.yml                    # Point d'entrée : import_playbook de chaque playbook de groupe
│   ├── <group>.yml                 # Un play par groupe : hosts, become, roles, tags
│   └── ping.yml                    # Smoke test de connectivité (ansible.builtin.ping)
│
└── roles/
    └── <role>/
        ├── README.md               # But du rôle, variables, dépendances, exemple d'usage
        ├── defaults/main.yml       # Variables surchargeables, chacune commentée (rôle + valeurs admises)
        ├── vars/main.yml           # Variables internes (ex. mapping paquets par OS)
        ├── tasks/main.yml          # Tâches nommées, modules FQCN, tags
        ├── handlers/main.yml       # Handlers nommés (restart/reload de services)
        ├── templates/*.j2          # Templates de config, en-tête « fichier géré par Ansible »
        ├── files/                  # Fichiers statiques (+ .gitkeep si vide)
        └── meta/main.yml           # galaxy_info, plateformes supportées, dependencies
```

**Précédence des variables** (documentée dans le README généré) :
`roles/*/defaults` < `group_vars/all.yml` < `group_vars/<group>.yml` < `inventories/<env>/group_vars/all.yml` < `inventories/<env>/group_vars/<group>.yml` < `inventories/<env>/host_vars/<host>.yml`

---

## 3. Architecture de l'outil

```
ansible-forge/
├── CLAUDE.md
├── pyproject.toml
├── README.md
├── docs/design.md
├── src/ansible_forge/
│   ├── __init__.py            # __version__
│   ├── __main__.py            # python -m ansible_forge
│   ├── cli.py                 # Typer : new / generate / validate / catalog
│   ├── errors.py              # ForgeError et sous-classes (sortie CLI propre)
│   ├── models/
│   │   ├── spec.py            # ProjectSpec, EnvironmentSpec, GroupSpec, HostSpec, RoleConfig
│   │   └── enums.py           # OSFamily, FirewallBackend
│   ├── spec_io.py             # load_spec / save_spec (YAML), champ spec_version
│   ├── catalog/
│   │   ├── registry.py        # RoleDefinition + ROLE_CATALOG (ordonné)
│   │   └── roles/*.py         # 1 module par rôle : questions, defaults, collections, deps
│   ├── prompts/
│   │   ├── flow.py            # Orchestration questionary (§1)
│   │   └── validators.py      # Validateurs partagés questionary ↔ pydantic
│   ├── engine/
│   │   ├── renderer.py        # Fabrique l'Environment Jinja2 (réglages déterministes)
│   │   ├── filters.py         # to_nice_yaml, comment_block, quote_smart
│   │   ├── planner.py         # ProjectSpec -> list[Artifact]  (aucune I/O)
│   │   └── writer.py          # Artifact -> disque ; arbre pour --dry-run
│   └── templates/
│       ├── partials/          # header.j2, var_doc.j2
│       ├── project/           # ansible.cfg.j2, inventory/, vars/, playbooks/
│       └── roles/<role>/…     # miroir de l'arbre du rôle, chaque fichier en .j2
└── tests/
    ├── test_models.py             # validation, défauts, erreurs
    ├── test_spec_io.py            # round-trip YAML, spec_version
    ├── test_determinism.py        # 2 rendus successifs identiques octet pour octet
    ├── test_planner.py            # chemins/artifacts attendus selon la spec
    ├── test_golden.py             # comparaison fichier par fichier vs tests/golden/
    ├── test_ansible_validation.py # --syntax-check + ansible-lint (skip si absents)
    ├── specs/*.yml                # specs d'exemple (minimal, full, multi-env)
    └── golden/<spec_name>/…       # sortie de référence
```

### Modèle de données (pydantic v2)
```python
HostSpec(name, ansible_host, ansible_port|None, ansible_user|None, vars: dict)
GroupSpec(name, description, roles: list[str], vars: dict)
EnvironmentSpec(name, hosts: dict[group_name, list[HostSpec]], group_vars: dict[str, dict])
RoleConfig(name, enabled, options: dict)          # réponses aux questions du rôle
ProjectSpec(
  spec_version, project_name, description, author,
  os_family, remote_user, become, ssh_port, python_interpreter,
  environments: list[EnvironmentSpec],
  groups: list[GroupSpec],
  roles: list[RoleConfig],
  options: GenerationOptions,
)
```
Validateurs croisés : tout groupe référencé par un hôte existe ; tout rôle référencé est au catalogue ; noms uniques ; ≥ 1 environnement ; ≥ 1 groupe.

### Garanties de déterminisme
- Jinja2 : `trim_blocks`, `lstrip_blocks`, `keep_trailing_newline`, `undefined=StrictUndefined`.
- Aucune date, aucun `random`, aucun `os.getlogin()`, aucun chemin absolu dans la sortie.
- Toute itération sur dict/ensemble est triée explicitement.
- Écriture en `\n`, UTF-8 sans BOM, permissions fixes (0644 / 0755).
- `planner` est pur (spec → artifacts en mémoire) : `--dry-run` et les golden tests partagent ce code.

### Commandes CLI
- `ansible-forge new [--output DIR] [--force]` — interactif, écrit `forge.yml` puis génère.
- `ansible-forge generate --spec forge.yml [--output DIR] [--force] [--dry-run]`
- `ansible-forge validate --spec forge.yml` — valide sans écrire.
- `ansible-forge catalog` — liste les rôles et leurs options.
- Régénération des références : `pytest --regen-golden` (option pytest, source unique de vérité).

---

## 4. Décisions — VALIDÉES le 2026-08-22

| # | Décision | Choix retenu |
|---|---|---|
| 1 | Emplacement des `group_vars` | **Racine + inventaire.** `group_vars/` racine = défauts projet ; `inventories/<env>/group_vars/` = surcharges d'environnement ; `host_vars/` uniquement sous `inventories/<env>/`. |
| 2 | Validation ansible-lint / syntax-check | **Les deux.** Boucle locale via WSL Debian (`/opt/forge-venv`), plus un workflow CI GitHub Actions comme porte finale. |
| 3 | Périmètre du catalogue de rôles | **Les 7 rôles**, implémentés et validés un par un. L'outil reste **générique** : le questionnaire cible le périmètre, la génération produit uniquement les rôles et playbooks correspondants. |
| 4 | Gestion des secrets | **`vault.yml.example` en clair** + doc `ansible-vault encrypt`. Aucun appel à `ansible-vault` (chiffrement salé ⇒ non déterministe). |

### Écarts assumés par rapport au design initial

| Point du design | Ce qui a été fait | Pourquoi |
|---|---|---|
| `prompts/validators.py` | Remonté en `ansible_forge/validation.py` | La couche modèle ne doit pas dépendre de la couche interactive ; les deux partagent désormais les mêmes règles. |
| `host_vars/` à la racine | Non généré | Une machine appartient toujours à un environnement ; un `host_vars/` racine n'aurait jamais de contenu. |
| `inventories/<env>/group_vars/all.yml` | Devenu `group_vars/all/main.yml` (répertoire) | Seule la forme répertoire permet à `vault.yml` d'être chargé pour toutes les machines de l'environnement. Un `vault.yml` posé à côté de `all.yml` s'appliquerait à un groupe nommé « vault », qui n'existe pas. |
| Commande `catalog` seule | Ajout de `ansible-forge check` | Donne un moyen intégré de vérifier qu'un projet passe `ansible-lint` et `--syntax-check`, et un message d'installation clair quand les outils manquent. |
| `RoleOption` | Ajout de `item_kind` | Le type des éléments d'une liste ne peut pas être deviné à partir d'une valeur par défaut vide. |

### Détail des recommandations (contexte)

1. **Emplacement des `group_vars`** — Ansible charge à la fois `<playbook_dir>/group_vars` et `<inventaire>/group_vars`. *Recommandation* : garder les deux, avec un rôle explicite (racine = défauts projet, inventaire = surcharges d'environnement) et la précédence documentée dans le README généré. Alternative plus sûre : tout mettre dans les inventaires (mais l'énoncé demande `group_vars/all.yml` à la racine).

2. **`host_vars/` à la racine** — inutile en pratique (les hôtes appartiennent à un environnement). *Recommandation* : ne générer `host_vars/` que sous `inventories/<env>/`, et ne pas créer de `host_vars/` racine.

3. **Validation ansible sur Windows** — `ansible-core` ne supporte pas Windows comme nœud de contrôle ; `ansible-playbook --syntax-check` et `ansible-lint` ne peuvent pas tourner ici. *Recommandation* : ces tests sont `skipif` (binaire absent ou `win32`), et sont exécutés dans un job CI GitHub Actions (ubuntu-latest) qui devient la porte de validation. Les tests golden + déterminisme, eux, tournent partout.

4. **Vault** — le chiffrement `ansible-vault` est salé, donc non déterministe. *Recommandation* : ne jamais appeler `ansible-vault` ; générer `vault.yml.example` en clair (valeurs factices) + une section README expliquant `ansible-vault encrypt`.

5. **Rôles : sources générées vs dépendances Galaxy** — *Recommandation* : générer le code source des rôles dans `roles/` (auto-suffisant et entièrement commenté, conforme à l'objectif). `requirements.yml` ne liste que les **collections** nécessaires (`community.general`, `ansible.posix`, `community.postgresql`, `community.docker`).

6. **Structure des playbooks** — *Recommandation* : `site.yml` fait `import_playbook` de `playbooks/<group>.yml` (un play par groupe). Plus lisible et permet de cibler un groupe seul.

7. **Format d'inventaire** — *Recommandation* : YAML (`hosts.yml`) plutôt qu'INI.

8. **Politique d'écriture** — *Recommandation* : refuser un dossier de sortie non vide sauf `--force` ; `--dry-run` affiche l'arbre sans rien écrire.
