# Role `users`

Local accounts: creation, secondary groups, sudo and authorised SSH keys.

## Variables

Every variable is defined in `defaults/main.yml` and can be overridden from
`group_vars/` or `host_vars/`.

| Variable | Purpose | Allowed values | Default |
|---|---|---|---|
| `users_accounts` | List of the local accounts managed by the role. | List of dictionaries (name, groups, sudo, shell, ssh_public_key, state). | `[]` |
| `users_manage_sudoers` | Writes a file in /etc/sudoers.d for the accounts marked sudo. | true or false. | `true` |
| `users_remove_absent_home` | Removes /home/<user> when the account moves to the absent state. | true or false. | `false` |

## Internal variables

Defined in `vars/main.yml`, they are not meant to be overridden.

- `users_sudoers_file`: name of the file written to /etc/sudoers.d
- `users_secondary_groups`: secondary groups derived from users_accounts
- `users_sudo_accounts`: present accounts that have sudo access

## Required collections

- `ansible.posix` — accepted versions: `>=2.2.2,<3.0.0`

These ranges are the ones of `requirements.yml`, at the root of the Ansible
project; that file is the one that counts at install time.

## Usage example

```yaml
- name: Apply the users role
  hosts: dbservers
  become: true
  roles:
    - role: users
```

## Supported systems

- Debian
- Ubuntu
