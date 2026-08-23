# ansible-forge

Générateur **déterministe** de projets Ansible complets et entièrement commentés.

Vous répondez à une série de questions ; l'outil écrit un projet Ansible prêt à
l'emploi — `ansible.cfg`, inventaires multi-environnements, `group_vars` /
`host_vars` commentés, playbooks et rôles — puis enregistre vos réponses dans
`forge.yml` pour pouvoir tout régénérer plus tard.

- **Aucun LLM, aucune API externe.** Tout passe par des templates Jinja2.
- **Même spécification ⇒ même sortie, octet pour octet.** C'est vérifié par des
  tests golden à chaque exécution de la suite.
- **Tout est commenté** : un en-tête dans chaque fichier, un `name:` sur chaque
  tâche, et pour chaque variable son rôle et ses valeurs admises.
- **Les projets générés passent `ansible-lint` (profil `production`) et
  `ansible-playbook --syntax-check`.** C'est un test, pas une promesse.

## Installation

```bash
python -m pip install ansible-forge
```

Depuis les sources :

```bash
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

Python 3.11+. Dépendances : `typer`, `questionary`, `jinja2`, `pyyaml`,
`pydantic`. `ansible-core` et `ansible-lint` ne sont **pas** nécessaires pour
générer un projet — seulement pour le vérifier avec `ansible-forge check`.

## Prise en main

```bash
ansible-forge new
```

L'entretien couvre : identité du projet, famille d'OS et connexion SSH,
environnements, groupes de machines et rôles appliqués à chacun, machines de
chaque environnement, réglages des rôles choisis, options de génération.
Une transcription complète est disponible dans
[docs/example-session.md](docs/example-session.md).

Puis, dans le projet généré :

```bash
ansible-galaxy collection install -r requirements.yml
ansible-playbook -i inventories/dev playbooks/ping.yml
ansible-playbook -i inventories/dev playbooks/site.yml --check --diff
```

## Commandes

| Commande | Rôle |
|---|---|
| `ansible-forge new` | Entretien interactif, écrit `forge.yml` puis génère le projet |
| `ansible-forge generate --spec forge.yml` | Rejoue une spécification, sans aucune question |
| `ansible-forge validate --spec forge.yml` | Vérifie une spécification et résume ce qu'elle produirait |
| `ansible-forge check <projet>` | Passe `--syntax-check` et `ansible-lint` sur un projet généré |
| `ansible-forge catalog [rôle]` | Liste les rôles disponibles et leurs options |

Options communes à `new` et `generate` :

| Option | Effet |
|---|---|
| `--output DIR` | Répertoire de sortie (défaut : `./<nom-du-projet>`) |
| `--force` | Autorise l'écriture dans un répertoire non vide |
| `--dry-run` | Affiche l'arborescence qui serait produite, sans rien écrire |

### Exemples

Prévisualiser avant d'écrire :

```bash
ansible-forge generate --spec forge.yml --dry-run
```

Régénérer un projet après avoir modifié `forge.yml` à la main :

```bash
ansible-forge generate --spec forge.yml --output plateforme-web --force
```

Voir les options d'un rôle avant de le sélectionner :

```bash
ansible-forge catalog postgresql
```

Contrôler un projet généré :

```bash
ansible-forge check plateforme-web
```

## Ce qui est généré

```text
<projet>/
├── ansible.cfg                 # inventaire par défaut, roles_path, réglages SSH
├── requirements.yml            # collections Galaxy déduites des rôles choisis
├── forge.yml                   # la spécification, pour régénérer à l'identique
├── README.md                   # doc du projet : commandes, précédence, secrets
├── .yamllint / .ansible-lint   # règles de qualité, cohérentes entre elles
├── inventories/<env>/
│   ├── hosts.yml               # groupes et machines de l'environnement
│   ├── group_vars/all/         # variables de l'environnement + modèle de vault
│   ├── group_vars/<groupe>.yml # surcharges du groupe dans cet environnement
│   └── host_vars/<machine>.yml # variables propres à une machine
├── group_vars/                 # défauts du projet (all.yml et <groupe>.yml)
├── playbooks/
│   ├── site.yml                # importe un playbook par groupe
│   ├── <groupe>.yml            # un play, les rôles du groupe, des tags
│   └── ping.yml                # test de connectivité, sans effet de bord
└── roles/<rôle>/               # defaults, vars, tasks, handlers, templates, README
```

Un exemple complet est livré dans [`examples/`](examples/) : la spécification
[`examples/forge.yml`](examples/forge.yml) et le projet qu'elle produit,
[`examples/plateforme-web/`](examples/plateforme-web/) — 3 environnements,
3 groupes, les 7 rôles du catalogue, 96 fichiers.

### Précédence des variables

De la plus faible à la plus forte :

1. `roles/<rôle>/defaults/main.yml` — valeurs par défaut du rôle, documentées
2. `group_vars/all.yml` — valeurs communes au projet
3. `group_vars/<groupe>.yml` — valeurs communes au groupe
4. `inventories/<env>/group_vars/all/main.yml` — valeurs de l'environnement
5. `inventories/<env>/group_vars/<groupe>.yml` — groupe dans cet environnement
6. `inventories/<env>/host_vars/<machine>.yml` — machine précise
7. `roles/<rôle>/vars/main.yml` — variables internes, non surchargeables

Seules les valeurs que vous avez **changées** sont écrites dans
`group_vars/all.yml`. Les autres restent documentées à un seul endroit, dans les
`defaults` du rôle : aucune duplication à maintenir.

## Catalogue de rôles

| Rôle | Objet | Collections requises |
|---|---|---|
| `common` | Paquets de base, fuseau horaire, NTP, bannière MOTD | `community.general` |
| `users` | Comptes locaux, groupes, sudo, clés SSH autorisées | `ansible.posix` |
| `ssh_hardening` | Durcissement OpenSSH par fichier `sshd_config.d` | — |
| `firewall` | ufw (Debian) ou firewalld (RedHat), politique et ports | `ansible.posix`, `community.general` |
| `nginx` | Serveur web, configuration globale et hôte virtuel, HTTPS optionnel | — |
| `docker` | Docker CE depuis le dépôt officiel, Compose, options du démon | — |
| `postgresql` | Serveur, réglages, rôles, bases, privilèges, `pg_hba` | `community.postgresql` |

Chaque rôle est généré avec son propre `README.md`, ses `defaults` commentés et
ses handlers. Les rôles ne se dépendent pas les uns des autres : c'est le
playbook du groupe qui fixe l'ordre d'application.

Les écritures sensibles sont validées avant d'être installées — `visudo -cf`
pour sudoers, `sshd -t` pour la configuration SSH, `nginx -t` pour nginx : une
erreur de syntaxe ne peut pas vous couper l'accès à la machine.

## Secrets

Le vault n'est jamais chiffré par l'outil : `ansible-vault` utilise un sel
aléatoire, donc la sortie ne serait pas reproductible. Un modèle en clair est
généré à la place :

```bash
cd inventories/prod/group_vars/all
cp vault.yml.example vault.yml
# remplacez les valeurs factices, puis :
ansible-vault encrypt vault.yml
```

`group_vars/all/` est volontairement un **répertoire** et non un fichier
`all.yml` : c'est la seule forme qui permette à `vault.yml` d'être chargé pour
toutes les machines de l'environnement.

## Développement

```bash
python -m pytest              # suite complète
python -m pytest --regen-golden   # régénère tests/golden/ après un changement voulu
```

Relisez toujours le `git diff` des références golden avant de le valider : c'est
la seule protection contre une modification involontaire du rendu.

### Vérification par les vrais outils Ansible

Les tests de `tests/test_ansible_validation.py` lancent réellement
`ansible-playbook --syntax-check` et `ansible-lint` sur chaque projet d'exemple.
`ansible-core` ne supportant pas Windows comme nœud de contrôle, ils passent par
WSL sous Windows et par le `PATH` ailleurs ; ils sont ignorés si aucun des deux
n'est disponible. La CI GitHub Actions (`ubuntu-latest`) fait autorité.

Configuration WSL reconnue par les tests :

| Variable | Défaut |
|---|---|
| `ANSIBLE_FORGE_WSL_DISTRO` | `Debian` |
| `ANSIBLE_FORGE_WSL_BIN` | `/opt/forge-venv/bin` |
| `ANSIBLE_FORGE_WSL_COLLECTIONS` | `/opt/forge-collections` |

### Architecture

```text
src/ansible_forge/
├── models/       ProjectSpec (pydantic) — la seule entrée du moteur
├── catalog/      les 7 rôles décrits comme des données : questions, défauts,
│                 valeurs admises, collections requises
├── prompts/      protocole Prompter + implémentation questionary
├── engine/       planner (pur : spec → artefacts en mémoire), renderer, writer
├── templates/    tous les fichiers générés, en Jinja2
├── verify.py     ansible-forge check
└── cli.py        typer
```

Le planificateur ne touche jamais au disque : `--dry-run`, les tests golden et
l'écriture réelle partagent exactement le même code. C'est ce qui rend le
déterminisme vérifiable plutôt que déclaratif.

Ajouter une option à un rôle se fait dans un seul fichier
(`catalog/roles/<rôle>.py`) : la question du questionnaire, la valeur par défaut,
le commentaire dans `defaults/main.yml` et la ligne du README du rôle en
découlent automatiquement.

## Licence

MIT.
