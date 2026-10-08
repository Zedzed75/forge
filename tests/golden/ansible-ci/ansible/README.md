# passerelle

Application gateway

**Maintainer:** Platform Team

> This project was generated from `forge.yml`, at the root of the repository. To
> regenerate it identically: `forge generate --only ansible`.

## Requirements

- A Linux or macOS control node with `ansible-core` >= 2.15
- Public-key SSH access to the target machines, with the `deploy`
  account on port 22
- `sudo` access on the target machines

Installing the dependencies:

```bash
ansible-galaxy collection install -r requirements.yml
```

## Layout

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

## Environments

| Environment | Inventory | Machines |
|---|---|---|
| `prod` | `inventories/prod` | 1 |

The `prod` environment is the one declared as the default in
`ansible.cfg`; the others are targeted with `-i`.

## Groups and roles

| Group | Description | Roles applied |
|---|---|---|
| `gateways` | Gateways exposed to the outside | common, ssh_hardening |

| Role | Purpose |
|---|---|
| [`common`](roles/common/README.md) | System baseline: base packages, time zone, NTP synchronisation, MOTD banner. |
| [`ssh_hardening`](roles/ssh_hardening/README.md) | OpenSSH hardening: root login, password authentication, limits. |

## Common commands

Check connectivity before anything else:

```bash
ansible-playbook -i inventories/prod playbooks/ping.yml
```

See what would change, without applying anything:

```bash
ansible-playbook -i inventories/prod playbooks/site.yml --check --diff
```

Apply the full configuration:

```bash
ansible-playbook -i inventories/prod playbooks/site.yml
```

Handle a single group only:

```bash
ansible-playbook -i inventories/prod playbooks/gateways.yml
```

Check the quality of the project:

```bash
ansible-playbook -i inventories/prod playbooks/site.yml --syntax-check
ansible-lint
yamllint .
```

## Variable precedence

From the weakest precedence to the strongest:

1. `roles/<role>/defaults/main.yml` — role defaults
2. `group_vars/all.yml` — values shared by the project
3. `group_vars/<group>.yml` — values shared by the group
4. `inventories/<env>/group_vars/all/main.yml` — values of the environment
5. `inventories/<env>/group_vars/<group>.yml` — the group in that environment
6. `inventories/<env>/host_vars/<machine>.yml` — one precise machine
7. `roles/<role>/vars/main.yml` — internal role variables, not overridable

Put every value at the most general level that fits: a value defined in
`host_vars` is invisible from the rest of the project.

## Secrets

No vault file was generated for this project. If you add secrets, encrypt them
with `ansible-vault` and never commit them in cleartext.

## Regenerating the project

`forge.yml` describes this project entirely. Edit it, then run again:

```bash
forge generate --only ansible --force
```

Every generated file carries a header saying so: your manual edits would be
lost there.

To receive only the evolutions of the template **without** losing your changes,
prefer:

```bash
forge update --only ansible
```
