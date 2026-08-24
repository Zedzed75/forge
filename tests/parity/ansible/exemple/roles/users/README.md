# Rôle `users`

Comptes locaux : création, groupes secondaires, sudo et clés SSH autorisées.

## Variables

Toutes les variables sont définies dans `defaults/main.yml` et peuvent être
surchargées depuis `group_vars/` ou `host_vars/`.

| Variable | Rôle | Valeurs admises | Défaut |
|---|---|---|---|
| `users_accounts` | Liste des comptes locaux gérés par le rôle. | Liste de dictionnaires (name, groups, sudo, shell, ssh_public_key, state). | `[]` |
| `users_manage_sudoers` | Écrit un fichier dans /etc/sudoers.d pour les comptes marqués sudo. | true ou false. | `true` |
| `users_remove_absent_home` | Supprime /home/<user> lorsque le compte passe à l'état absent. | true ou false. | `false` |

## Variables internes

Définies dans `vars/main.yml`, elles ne sont pas destinées à être surchargées.

- `users_sudoers_file` : nom du fichier déposé dans /etc/sudoers.d
- `users_secondary_groups` : groupes secondaires déduits de users_accounts
- `users_sudo_accounts` : comptes présents disposant d'un accès sudo

## Collections requises

- `ansible.posix`

## Exemple d'utilisation

```yaml
- name: Appliquer le rôle users
  hosts: webservers
  become: true
  roles:
    - role: users
```

## Systèmes supportés

- Debian
- Ubuntu
