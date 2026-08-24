# Rôle `ssh_hardening`

Durcissement OpenSSH : connexion root, authentification par mot de passe, limites.

## Variables

Toutes les variables sont définies dans `defaults/main.yml` et peuvent être
surchargées depuis `group_vars/` ou `host_vars/`.

| Variable | Rôle | Valeurs admises | Défaut |
|---|---|---|---|
| `ssh_hardening_port` | Port TCP sur lequel sshd écoute. | Entier de 1 à 65535. | `22` |
| `ssh_hardening_permit_root_login` | Valeur de la directive PermitRootLogin. | yes, no, prohibit-password ou forced-commands-only. | `prohibit-password` |
| `ssh_hardening_password_authentication` | Valeur de la directive PasswordAuthentication. | true ou false. | `false` |
| `ssh_hardening_pubkey_authentication` | Valeur de la directive PubkeyAuthentication. | true ou false. | `true` |
| `ssh_hardening_x11_forwarding` | Valeur de la directive X11Forwarding. | true ou false. | `false` |
| `ssh_hardening_max_auth_tries` | Valeur de la directive MaxAuthTries. | Entier de 1 à 10. | `3` |
| `ssh_hardening_allow_groups` | Valeur de la directive AllowGroups ; vide désactive la directive. | Liste de noms de groupes système. | `[]` |

## Variables internes

Définies dans `vars/main.yml`, elles ne sont pas destinées à être surchargées.

- `ssh_hardening_dropin_dir` : répertoire des fichiers de configuration additionnels de sshd
- `ssh_hardening_service` : nom du service SSH, résolu selon la famille d'OS

## Handlers

- `Redémarrer le service SSH`

## Exemple d'utilisation

```yaml
- name: Appliquer le rôle ssh_hardening
  hosts: webservers
  become: true
  roles:
    - role: ssh_hardening
```

## Systèmes supportés

- Debian
- Ubuntu
