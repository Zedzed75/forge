# boutique

Boutique en ligne, deployee sur Kubernetes et administree par Ansible

**Responsable :** Equipe Plateforme

> Ce projet a été généré à partir de `forge.yml`, à la racine du dépôt. Pour
> le régénérer à l'identique : `forge generate --only ansible`.

## Prérequis

- Un nœud de contrôle Linux ou macOS avec `ansible-core` >= 2.15
- Un accès SSH par clé publique aux machines cibles, avec le compte
  `deploy` sur le port 22
- Un accès `sudo` sur les machines cibles

Installation des dépendances :

```bash
ansible-galaxy collection install -r requirements.yml
```

## Arborescence

```text
boutique/
├── group_vars/
│   ├── all.yml
│   └── dbservers.yml
├── inventories/
│   ├── dev/
│   │   ├── group_vars/
│   │   │   ├── all/
│   │   │   │   ├── main.yml
│   │   │   │   └── vault.yml.example
│   │   │   └── dbservers.yml
│   │   ├── host_vars/
│   │   │   └── db-dev-01.yml
│   │   └── hosts.yml
│   └── prod/
│       ├── group_vars/
│       │   ├── all/
│       │   │   ├── main.yml
│       │   │   └── vault.yml.example
│       │   └── dbservers.yml
│       ├── host_vars/
│       │   └── db-prod-01.yml
│       └── hosts.yml
├── playbooks/
│   ├── dbservers.yml
│   ├── ping.yml
│   └── site.yml
├── roles/
│   ├── common/
│   │   ├── defaults/
│   │   │   └── main.yml
│   │   ├── handlers/
│   │   │   └── main.yml
│   │   ├── meta/
│   │   │   └── main.yml
│   │   ├── tasks/
│   │   │   └── main.yml
│   │   ├── templates/
│   │   │   └── motd.j2
│   │   ├── vars/
│   │   │   └── main.yml
│   │   └── README.md
│   ├── firewall/
│   │   ├── defaults/
│   │   │   └── main.yml
│   │   ├── handlers/
│   │   │   └── main.yml
│   │   ├── meta/
│   │   │   └── main.yml
│   │   ├── tasks/
│   │   │   ├── firewalld.yml
│   │   │   ├── main.yml
│   │   │   └── ufw.yml
│   │   ├── vars/
│   │   │   └── main.yml
│   │   └── README.md
│   ├── postgresql/
│   │   ├── defaults/
│   │   │   └── main.yml
│   │   ├── handlers/
│   │   │   └── main.yml
│   │   ├── meta/
│   │   │   └── main.yml
│   │   ├── tasks/
│   │   │   └── main.yml
│   │   ├── vars/
│   │   │   └── main.yml
│   │   └── README.md
│   ├── ssh_hardening/
│   │   ├── defaults/
│   │   │   └── main.yml
│   │   ├── handlers/
│   │   │   └── main.yml
│   │   ├── meta/
│   │   │   └── main.yml
│   │   ├── tasks/
│   │   │   └── main.yml
│   │   ├── templates/
│   │   │   └── hardening.conf.j2
│   │   ├── vars/
│   │   │   └── main.yml
│   │   └── README.md
│   └── users/
│       ├── defaults/
│       │   └── main.yml
│       ├── meta/
│       │   └── main.yml
│       ├── tasks/
│       │   └── main.yml
│       ├── templates/
│       │   └── sudoers.j2
│       ├── vars/
│       │   └── main.yml
│       └── README.md
├── .ansible-lint
├── .gitignore
├── .yamllint
├── README.md
├── ansible.cfg
├── forge.yml
└── requirements.yml
```

## Environnements

| Environnement | Inventaire | Machines |
|---|---|---|
| `dev` | `inventories/dev` | 1 |
| `prod` | `inventories/prod` | 1 |

L'environnement `dev` est celui déclaré par défaut dans
`ansible.cfg` ; les autres se ciblent avec `-i`.

## Groupes et rôles

| Groupe | Description | Rôles appliqués |
|---|---|---|
| `dbservers` | Serveurs de base de donnees, hors cluster | common, users, ssh_hardening, firewall, postgresql |

| Rôle | Objet |
|---|---|
| [`common`](roles/common/README.md) | Socle système : paquets de base, fuseau horaire, synchronisation NTP, bannière MOTD. |
| [`users`](roles/users/README.md) | Comptes locaux : création, groupes secondaires, sudo et clés SSH autorisées. |
| [`ssh_hardening`](roles/ssh_hardening/README.md) | Durcissement OpenSSH : connexion root, authentification par mot de passe, limites. |
| [`firewall`](roles/firewall/README.md) | Pare-feu local : ufw (Debian) ou firewalld (RedHat), politique par défaut et ports ouverts. |
| [`postgresql`](roles/postgresql/README.md) | Serveur PostgreSQL : installation, écoute réseau, bases, rôles et règles pg_hba. |

## Commandes courantes

Vérifier la connectivité avant tout :

```bash
ansible-playbook -i inventories/dev playbooks/ping.yml
```

Voir ce qui serait modifié, sans rien appliquer :

```bash
ansible-playbook -i inventories/dev playbooks/site.yml --check --diff
```

Appliquer la configuration complète :

```bash
ansible-playbook -i inventories/dev playbooks/site.yml
```

Ne traiter qu'un seul groupe :

```bash
ansible-playbook -i inventories/dev playbooks/dbservers.yml
```

Contrôler la qualité du projet :

```bash
ansible-playbook -i inventories/dev playbooks/site.yml --syntax-check
ansible-lint
yamllint .
```

## Précédence des variables

De la précédence la plus faible à la plus forte :

1. `roles/<rôle>/defaults/main.yml` — valeurs par défaut du rôle
2. `group_vars/all.yml` — valeurs communes au projet
3. `group_vars/<groupe>.yml` — valeurs communes au groupe
4. `inventories/<env>/group_vars/all/main.yml` — valeurs de l'environnement
5. `inventories/<env>/group_vars/<groupe>.yml` — groupe dans cet environnement
6. `inventories/<env>/host_vars/<machine>.yml` — machine précise
7. `roles/<rôle>/vars/main.yml` — variables internes du rôle, non surchargeables

Placez chaque valeur au niveau le plus général qui convienne : une valeur
définie dans `host_vars` est invisible depuis le reste du projet.

## Secrets

Les secrets vivent dans `inventories/<env>/group_vars/all/vault.yml`, chiffré
avec `ansible-vault`. Un modèle en clair est fourni :

```bash
cd inventories/dev/group_vars/all
cp vault.yml.example vault.yml
# remplacez les valeurs factices, puis :
ansible-vault encrypt vault.yml
```

Exécutez ensuite les playbooks avec `--ask-vault-pass` ou
`--vault-password-file`. Le fichier chiffré peut être versionné ; le mot de
passe, jamais.

Le répertoire `group_vars/all/` est volontairement un répertoire et non un
fichier `all.yml` : c'est la seule forme qui permet à `vault.yml` d'être chargé
pour toutes les machines de l'environnement.

## Régénérer le projet

`forge.yml` décrit entièrement ce projet. Modifiez-le puis relancez :

```bash
forge generate --only ansible --force
```

Les fichiers générés portent tous un en-tête le rappelant : vos modifications
manuelles y seraient perdues.

Pour ne recevoir que les évolutions du gabarit **sans** perdre vos
modifications, préférez :

```bash
forge update --only ansible
```
