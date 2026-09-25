# Role `common`

System baseline: base packages, time zone, NTP synchronisation, MOTD banner.

## Variables

Every variable is defined in `defaults/main.yml` and can be overridden from
`group_vars/` or `host_vars/`.

| Variable | Purpose | Allowed values | Default |
|---|---|---|---|
| `common_timezone` | Time zone applied to every machine of the group. | Identifier from the tz database, for instance 'Europe/Paris' or 'UTC'. | `Europe/Paris` |
| `common_packages` | Packages installed on every machine of the group. | List of package names valid for the targeted OS family. | `_:
  - ca-certificates
  - curl
  - htop
  - vim` |
| `common_manage_timezone` | Enables the configuration of the time zone by the role. | true or false. | `true` |
| `common_enable_ntp` | Installs and enables time synchronisation (systemd-timesyncd). | true or false. | `true` |
| `common_manage_motd` | Deploys an /etc/motd file describing the purpose of the machine. | true or false. | `true` |

## Internal variables

Defined in `vars/main.yml`, they are not meant to be overridden.

- `common_ntp_package`: time synchronisation package resolved per OS family
- `common_ntp_service`: time synchronisation service resolved per OS family

## Handlers

- `Restart the time synchronisation service`

## Required collections

- `community.general` — accepted versions: `>=13.4.0,<14.0.0`

These ranges are the ones of `requirements.yml`, at the root of the Ansible
project; that file is the one that counts at install time.

## Usage example

```yaml
- name: Apply the common role
  hosts: dbservers
  become: true
  roles:
    - role: common
```

## Supported systems

- Debian
- Ubuntu
