# Role `firewall`

Local firewall: ufw (Debian) or firewalld (RedHat), default policy and open ports.

## Variables

Every variable is defined in `defaults/main.yml` and can be overridden from
`group_vars/` or `host_vars/`.

| Variable | Purpose | Allowed values | Default |
|---|---|---|---|
| `firewall_backend` | Backend used; 'auto' picks ufw on Debian and firewalld on RedHat. | auto, ufw or firewalld. | `auto` |
| `firewall_default_incoming_policy` | Action applied to incoming traffic that is not explicitly allowed. | deny, reject or allow. | `deny` |
| `firewall_default_outgoing_policy` | Action applied to outgoing traffic that is not explicitly allowed. | allow, deny or reject. | `allow` |
| `firewall_allowed_tcp_ports` | TCP ports opened for inbound traffic. | List of integers from 1 to 65535. | `_:
  - 22
  - 80
  - 443` |
| `firewall_allowed_udp_ports` | UDP ports opened for inbound traffic. | List of integers from 1 to 65535. | `[]` |
| `firewall_enabled` | Enables and starts the firewall service. | true or false. | `true` |
| `firewall_log_level` | Verbosity of the firewall logs. | off, low, medium, high or full. | `low` |

## Internal variables

Defined in `vars/main.yml`, they are not meant to be overridden.

- `firewall_effective_backend`: backend actually used, once "auto" is resolved
- `firewall_zone`: firewalld zone the rules are set in
- `firewall_zone_target`: firewalld zone target derived from the default policy

## Handlers

- `Reload the firewall`

## Required collections

- `ansible.posix` — accepted versions: `>=2.2.2,<3.0.0`
- `community.general` — accepted versions: `>=13.4.0,<14.0.0`

These ranges are the ones of `requirements.yml`, at the root of the Ansible
project; that file is the one that counts at install time.

## Usage example

```yaml
- name: Apply the firewall role
  hosts: dbservers
  become: true
  roles:
    - role: firewall
```

## Supported systems

- Debian
- Ubuntu
