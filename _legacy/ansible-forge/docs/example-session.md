# Exemple de session complète

Transcription réelle, produite en rejouant le questionnaire d'`ansible-forge new`
puis en exécutant les commandes de la CLI. Les questions et leurs valeurs par
défaut (entre crochets) sont celles du code ; rien n'est reconstitué à la main.

## 1. `ansible-forge new` — l'entretien

```text
$ ansible-forge new

── Identité du projet ──
  ? Nom du projet
    [mon-projet] > plateforme-web
  ? Description courte du projet
    [] > Plateforme web interne : frontaux nginx et base de donnees
  ? Auteur ou équipe responsable
    [] > Equipe Infrastructure

── Machines cibles et connexion ──
  ? Famille de système d'exploitation cible
    (debian / redhat) > debian
  ? Compte SSH utilisé par Ansible
    [ansible] > deploy
  ? Port SSH des machines cibles
    [22] > 2222
  ? Utiliser sudo (escalade de privilèges) ? [O/n] > oui
  ? Interpréteur Python distant
    [auto_silent] > auto_silent

── Environnements ──
  ? Environnements à générer
    (dev staging prod) > dev, prod
  ? Environnements supplémentaires (séparés par des virgules, vide si aucun)
    [] > 

── Groupes de machines ──
  ? Nom du groupe n°1
    [webservers] > webservers
  ? Description du groupe « webservers »
    [] > Serveurs web frontaux
  ? Rôles appliqués au groupe « webservers »
    (common users ssh_hardening firewall nginx docker postgresql) > common
  ? Ajouter un autre groupe ? [o/N] > oui
  ? Nom du groupe n°2
    [] > dbservers
  ? Description du groupe « dbservers »
    [] > Serveurs de base de donnees
  ? Rôles appliqués au groupe « dbservers »
    (common users ssh_hardening firewall nginx docker postgresql) > common
  ? Ajouter un autre groupe ? [o/N] > non

── Machines ──
  ? Préciser un port ou un compte SSH spécifique par machine ? [o/N] > non
  ? Nombre de machines dans « webservers » pour l'environnement « dev »
    [1] > 2
  ?   Nom de la machine 1/2 (webservers/dev)
    [webservers-dev-01] > webservers-dev-01
  ?   Adresse IP ou nom de domaine de « webservers-dev-01 »
    [] > 10.10.0.11
  ?   Nom de la machine 2/2 (webservers/dev)
    [webservers-dev-02] > webservers-dev-02
  ?   Adresse IP ou nom de domaine de « webservers-dev-02 »
    [] > 10.10.0.12
  ? Nombre de machines dans « dbservers » pour l'environnement « dev »
    [1] > 1
  ?   Nom de la machine 1/1 (dbservers/dev)
    [dbservers-dev-01] > dbservers-dev-01
  ?   Adresse IP ou nom de domaine de « dbservers-dev-01 »
    [] > 10.10.0.21
  ? Nombre de machines dans « webservers » pour l'environnement « prod »
    [1] > 2
  ?   Nom de la machine 1/2 (webservers/prod)
    [webservers-prod-01] > webservers-prod-01
  ?   Adresse IP ou nom de domaine de « webservers-prod-01 »
    [] > 10.30.0.11
  ?   Nom de la machine 2/2 (webservers/prod)
    [webservers-prod-02] > webservers-prod-02
  ?   Adresse IP ou nom de domaine de « webservers-prod-02 »
    [] > 10.30.0.12
  ? Nombre de machines dans « dbservers » pour l'environnement « prod »
    [1] > 1
  ?   Nom de la machine 1/1 (dbservers/prod)
    [dbservers-prod-01] > dbservers-prod-01
  ?   Adresse IP ou nom de domaine de « dbservers-prod-01 »
    [] > 10.30.0.21

── Réglages des rôles ──
  ? Personnaliser les réglages des rôles ? (non = valeurs par défaut documentées) [o/N] > oui

Rôle « common » — Socle système : paquets de base, fuseau horaire, synchronisation NTP, bannière MOTD.
  ? Fuseau horaire des machines
    [Europe/Paris] > Europe/Paris
  ? Paquets de base à installer (séparés par des virgules) [Liste de noms de paquets valides pour la famille d'OS ciblée.]
    [ca-certificates, curl, htop, vim] > ca-certificates, curl, htop, vim, rsync
  ? Gérer le fuseau horaire ? [O/n] > oui
  ? Activer la synchronisation NTP ? [O/n] > oui
  ? Générer une bannière MOTD ? [O/n] > oui

── Options de génération ──
  ? Générer les modèles de fichiers vault (secrets) ? [O/n] > oui
  ? Générer .gitignore, .yamllint et .ansible-lint ? [O/n] > oui
  ? Copier forge.yml dans le projet généré (rejouabilité) ? [O/n] > oui

Spécification enregistrée : forge.yml
```

## 2. La spécification produite — `forge.yml`

```yaml
# ---------------------------------------------------------------------------
# forge.yml - Spécification du projet Ansible
# ---------------------------------------------------------------------------
# Ce fichier décrit entièrement le projet à générer. Il est rejouable :
#   ansible-forge generate --spec forge.yml
# produit exactement la même arborescence, octet pour octet.
#
# Éditez-le à la main puis relancez la génération ; ne modifiez pas
# 'spec_version' manuellement.
# ---------------------------------------------------------------------------
spec_version: 1
project_name: plateforme-web
description: 'Plateforme web interne : frontaux nginx et base de donnees'
author: Equipe Infrastructure
os_family: debian
remote_user: deploy
become: true
ssh_port: 2222
python_interpreter: auto_silent
environments:
  - name: dev
    hosts:
      webservers:
        - name: webservers-dev-01
          ansible_host: 10.10.0.11
          ansible_port: null
          ansible_user: null
          vars: {}
        - name: webservers-dev-02
          ansible_host: 10.10.0.12
          ansible_port: null
          ansible_user: null
          vars: {}
      dbservers:
        - name: dbservers-dev-01
          ansible_host: 10.10.0.21
          ansible_port: null
          ansible_user: null
          vars: {}
    group_vars: {}
  - name: prod
    hosts:
      webservers:
        - name: webservers-prod-01
          ansible_host: 10.30.0.11
          ansible_port: null
          ansible_user: null
          vars: {}
        - name: webservers-prod-02
          ansible_host: 10.30.0.12
          ansible_port: null
          ansible_user: null
          vars: {}
      dbservers:
        - name: dbservers-prod-01
          ansible_host: 10.30.0.21
          ansible_port: null
          ansible_user: null
          vars: {}
    group_vars: {}
groups:
  - name: webservers
    description: Serveurs web frontaux
    roles:
      - common
    vars: {}
  - name: dbservers
    description: Serveurs de base de donnees
    roles:
      - common
    vars: {}
roles:
  - name: common
    options:
      timezone: Europe/Paris
      packages:
        - ca-certificates
        - curl
        - htop
        - vim
        - rsync
      manage_timezone: true
      enable_ntp: true
      manage_motd: true
options:
  use_vault: true
  write_lint_config: true
  embed_spec: true
  write_ci: false
```

## 3. `ansible-forge generate --dry-run` — l'aperçu

```text
$ ansible-forge generate --spec forge.yml --dry-run
plateforme-web/
├── group_vars/
│   ├── all.yml
│   ├── dbservers.yml
│   └── webservers.yml
├── inventories/
│   ├── dev/
│   │   ├── group_vars/
│   │   │   ├── all/
│   │   │   │   ├── main.yml
│   │   │   │   └── vault.yml.example
│   │   │   ├── dbservers.yml
│   │   │   └── webservers.yml
│   │   ├── host_vars/
│   │   │   ├── dbservers-dev-01.yml
│   │   │   ├── webservers-dev-01.yml
│   │   │   └── webservers-dev-02.yml
│   │   └── hosts.yml
│   └── prod/
│       ├── group_vars/
│       │   ├── all/
│       │   │   ├── main.yml
│       │   │   └── vault.yml.example
│       │   ├── dbservers.yml
│       │   └── webservers.yml
│       ├── host_vars/
│       │   ├── dbservers-prod-01.yml
│       │   ├── webservers-prod-01.yml
│       │   └── webservers-prod-02.yml
│       └── hosts.yml
├── playbooks/
│   ├── dbservers.yml
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

37 fichiers seraient générés dans plateforme-web.

Mode --dry-run : aucun fichier n'a été écrit.
```

## 4. `ansible-forge generate` — la génération

```text
$ ansible-forge generate --spec forge.yml
Projet généré : Z:\vm\zedux\partage\repo\ansible-forge\.tmp\session\plateforme-web  (37 fichiers)

Étapes suivantes :
  cd plateforme-web
  ansible-galaxy collection install -r requirements.yml
  ansible-playbook -i inventories/dev playbooks/ping.yml
```

## 5. `ansible-forge validate` — le contrôle sans écriture

```text
$ ansible-forge validate --spec forge.yml
Spécification valide : forge.yml
  Projet         : plateforme-web
  Environnements : dev, prod
  Groupes        : webservers, dbservers
  Rôles          : common
  Fichiers       : 37
```

## 6. Rejouabilité

`forge.yml` est copié dans le projet généré. Le régénérer depuis cette copie
produit une arborescence identique octet pour octet — c'est vérifié par le test
`tests/test_cli.py::test_le_projet_genere_est_rejouable`.

```bash
ansible-forge generate --spec plateforme-web/forge.yml --output copie
diff -r plateforme-web copie   # aucune différence
```
