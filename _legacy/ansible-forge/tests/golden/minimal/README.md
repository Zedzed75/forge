# minimal-infra

Projet minimal à un seul groupe et un seul environnement

**Responsable :** Equipe Infra

> Ce projet a été généré à partir de `forge.yml`. Pour le régénérer à
> l'identique : `ansible-forge generate --spec forge.yml`.

## Prérequis

- Un nœud de contrôle Linux ou macOS avec `ansible-core` >= 2.15
- Un accès SSH par clé publique aux machines cibles, avec le compte
  `ansible` sur le port 22
- Un accès `sudo` sur les machines cibles

Installation des dépendances :

```bash
ansible-galaxy collection install -r requirements.yml
```

## Arborescence

```text
minimal-infra/
├── group_vars/
│   ├── all.yml
│   └── webservers.yml
├── inventories/
│   └── dev/
│       ├── group_vars/
│       │   ├── all/
│       │   │   ├── main.yml
│       │   │   └── vault.yml.example
│       │   └── webservers.yml
│       ├── host_vars/
│       │   └── web-dev-01.yml
│       └── hosts.yml
├── playbooks/
│   ├── ping.yml
│   ├── site.yml
│   └── webservers.yml
├── roles/
│   └── common/
│       ├── defaults/
│       │   └── main.yml
│       ├── handlers/
│       │   └── main.yml
│       ├── meta/
│       │   └── main.yml
│       ├── tasks/
│       │   └── main.yml
│       ├── templates/
│       │   └── motd.j2
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

L'environnement `dev` est celui déclaré par défaut dans
`ansible.cfg` ; les autres se ciblent avec `-i`.

## Groupes et rôles

| Groupe | Description | Rôles appliqués |
|---|---|---|
| `webservers` | Serveurs web frontaux | common |

| Rôle | Objet |
|---|---|
| [`common`](roles/common/README.md) | Socle système : paquets de base, fuseau horaire, synchronisation NTP, bannière MOTD. |

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
ansible-playbook -i inventories/dev playbooks/webservers.yml
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
ansible-forge generate --spec forge.yml --output . --force
```

Les fichiers générés portent tous un en-tête le rappelant : vos modifications
manuelles y seraient perdues.
