# boutique

Online store, deployed on Kubernetes and managed by Ansible

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
boutique/
├── group_vars/
│   ├── all.yml
│   └── dbservers.yml
├── inventories/
│   ├── dev/
│   │   ├── group_vars/
│   │   │   ├── all/
│   │   │   │   ├── main.yml
│   │   │   │   └── vault.yml.example
│   │   │   └── dbservers.yml
│   │   ├── host_vars/
│   │   │   └── db-dev-01.yml
│   │   └── hosts.yml
│   └── prod/
│       ├── group_vars/
│       │   ├── all/
│       │   │   ├── main.yml
│       │   │   └── vault.yml.example
│       │   └── dbservers.yml
│       ├── host_vars/
│       │   └── db-prod-01.yml
│       └── hosts.yml
├── playbooks/
│   ├── dbservers.yml
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
│   ├── firewall/
│   │   ├── defaults/
│   │   │   └── main.yml
│   │   ├── handlers/
│   │   │   └── main.yml
│   │   ├── meta/
│   │   │   └── main.yml
│   │   ├── tasks/
│   │   │   ├── firewalld.yml
│   │   │   ├── main.yml
│   │   │   └── ufw.yml
│   │   ├── vars/
│   │   │   └── main.yml
│   │   └── README.md
│   ├── postgresql/
│   │   ├── defaults/
│   │   │   └── main.yml
│   │   ├── handlers/
│   │   │   └── main.yml
│   │   ├── meta/
│   │   │   └── main.yml
│   │   ├── tasks/
│   │   │   └── main.yml
│   │   ├── vars/
│   │   │   └── main.yml
│   │   └── README.md
│   ├── ssh_hardening/
│   │   ├── defaults/
│   │   │   └── main.yml
│   │   ├── handlers/
│   │   │   └── main.yml
│   │   ├── meta/
│   │   │   └── main.yml
│   │   ├── tasks/
│   │   │   └── main.yml
│   │   ├── templates/
│   │   │   └── hardening.conf.j2
│   │   ├── vars/
│   │   │   └── main.yml
│   │   └── README.md
│   └── users/
│       ├── defaults/
│       │   └── main.yml
│       ├── meta/
│       │   └── main.yml
│       ├── tasks/
│       │   └── main.yml
│       ├── templates/
│       │   └── sudoers.j2
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
| `dev` | `inventories/dev` | 1 |
| `prod` | `inventories/prod` | 1 |

The `dev` environment is the one declared as the default in
`ansible.cfg`; the others are targeted with `-i`.

## Groups and roles

| Group | Description | Roles applied |
|---|---|---|
| `dbservers` | Database servers, outside the cluster | common, users, ssh_hardening, firewall, postgresql |

| Role | Purpose |
|---|---|
| [`common`](roles/common/README.md) | System baseline: base packages, time zone, NTP synchronisation, MOTD banner. |
| [`users`](roles/users/README.md) | Local accounts: creation, secondary groups, sudo and authorised SSH keys. |
| [`ssh_hardening`](roles/ssh_hardening/README.md) | OpenSSH hardening: root login, password authentication, limits. |
| [`firewall`](roles/firewall/README.md) | Local firewall: ufw (Debian) or firewalld (RedHat), default policy and open ports. |
| [`postgresql`](roles/postgresql/README.md) | PostgreSQL server: installation, network listening, databases, roles and pg_hba rules. |

## Common commands

Check connectivity before anything else:

```bash
ansible-playbook -i inventories/dev playbooks/ping.yml
```

See what would change, without applying anything:

```bash
ansible-playbook -i inventories/dev playbooks/site.yml --check --diff
```

Apply the full configuration:

```bash
ansible-playbook -i inventories/dev playbooks/site.yml
```

Handle a single group only:

```bash
ansible-playbook -i inventories/dev playbooks/dbservers.yml
```

Check the quality of the project:

```bash
ansible-playbook -i inventories/dev playbooks/site.yml --syntax-check
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

Secrets live in `inventories/<env>/group_vars/all/vault.yml`, encrypted with
`ansible-vault`. A cleartext template is provided:

```bash
cd inventories/dev/group_vars/all
cp vault.yml.example vault.yml
# replace the placeholder values, then:
ansible-vault encrypt vault.yml
```

Then run the playbooks with `--ask-vault-pass` or `--vault-password-file`. The
encrypted file may be committed; the password, never.

The `group_vars/all/` directory is deliberately a directory rather than an
`all.yml` file: it is the only form that lets `vault.yml` be loaded for every
machine of the environment.

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
