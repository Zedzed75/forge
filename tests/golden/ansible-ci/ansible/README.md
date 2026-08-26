# passerelle

Passerelle applicative

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
passerelle/
├── .github/
│   └── workflows/
│       └── ansible-lint.yml
├── group_vars/
│   ├── all.yml
│   └── gateways.yml
├── inventories/
│   └── prod/
│       ├── group_vars/
│       │   ├── all/
│       │   │   └── main.yml
│       │   └── gateways.yml
│       ├── host_vars/
│       │   └── gw-prod-01.yml
│       └── hosts.yml
├── playbooks/
│   ├── gateways.yml
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
│   └── ssh_hardening/
│       ├── defaults/
│       │   └── main.yml
│       ├── handlers/
│       │   └── main.yml
│       ├── meta/
│       │   └── main.yml
│       ├── tasks/
│       │   └── main.yml
│       ├── templates/
│       │   └── hardening.conf.j2
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
| `prod` | `inventories/prod` | 1 |

L'environnement `prod` est celui déclaré par défaut dans
`ansible.cfg` ; les autres se ciblent avec `-i`.

## Groupes et rôles

| Groupe | Description | Rôles appliqués |
|---|---|---|
| `gateways` | Passerelles exposées | common, ssh_hardening |

| Rôle | Objet |
|---|---|
| [`common`](roles/common/README.md) | Socle système : paquets de base, fuseau horaire, synchronisation NTP, bannière MOTD. |
| [`ssh_hardening`](roles/ssh_hardening/README.md) | Durcissement OpenSSH : connexion root, authentification par mot de passe, limites. |

## Commandes courantes

Vérifier la connectivité avant tout :

```bash
ansible-playbook -i inventories/prod playbooks/ping.yml
```

Voir ce qui serait modifié, sans rien appliquer :

```bash
ansible-playbook -i inventories/prod playbooks/site.yml --check --diff
```

Appliquer la configuration complète :

```bash
ansible-playbook -i inventories/prod playbooks/site.yml
```

Ne traiter qu'un seul groupe :

```bash
ansible-playbook -i inventories/prod playbooks/gateways.yml
```

Contrôler la qualité du projet :

```bash
ansible-playbook -i inventories/prod playbooks/site.yml --syntax-check
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

Aucun fichier de vault n'a été généré pour ce projet. Si vous ajoutez des
secrets, chiffrez-les avec `ansible-vault` et ne les versionnez jamais en clair.

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
