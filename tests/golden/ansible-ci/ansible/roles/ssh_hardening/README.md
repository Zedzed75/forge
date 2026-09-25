# Role `ssh_hardening`

OpenSSH hardening: root login, password authentication, limits.

## Variables

Every variable is defined in `defaults/main.yml` and can be overridden from
`group_vars/` or `host_vars/`.

| Variable | Purpose | Allowed values | Default |
|---|---|---|---|
| `ssh_hardening_port` | TCP port sshd listens on. | Integer from 1 to 65535. | `22` |
| `ssh_hardening_permit_root_login` | Value of the PermitRootLogin directive. | yes, no, prohibit-password or forced-commands-only. | `prohibit-password` |
| `ssh_hardening_password_authentication` | Value of the PasswordAuthentication directive. | true or false. | `false` |
| `ssh_hardening_pubkey_authentication` | Value of the PubkeyAuthentication directive. | true or false. | `true` |
| `ssh_hardening_x11_forwarding` | Value of the X11Forwarding directive. | true or false. | `false` |
| `ssh_hardening_max_auth_tries` | Value of the MaxAuthTries directive. | Integer from 1 to 10. | `3` |
| `ssh_hardening_allow_groups` | Value of the AllowGroups directive; empty disables the directive. | List of system group names. | `[]` |

## Internal variables

Defined in `vars/main.yml`, they are not meant to be overridden.

- `ssh_hardening_dropin_dir`: directory of the additional configuration files of sshd
- `ssh_hardening_service`: name of the SSH service, resolved per OS family

## Handlers

- `Restart the SSH service`

## Usage example

```yaml
- name: Apply the ssh_hardening role
  hosts: gateways
  become: true
  roles:
    - role: ssh_hardening
```

## Supported systems

- Debian
- Ubuntu
