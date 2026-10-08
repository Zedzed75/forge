# Role `postgresql`

PostgreSQL server: installation, network listening, databases, roles and pg_hba rules.

## Variables

Every variable is defined in `defaults/main.yml` and can be overridden from
`group_vars/` or `host_vars/`.

| Variable | Purpose | Allowed values | Default |
|---|---|---|---|
| `postgresql_version` | Major version installed from the repositories of the distribution. | Major version number, for instance '15' or '16'. | `'16'` |
| `postgresql_listen_addresses` | Value of listen_addresses in postgresql.conf. | 'localhost', '*' or a comma-separated list of addresses. | `localhost` |
| `postgresql_port` | TCP port of the PostgreSQL server. | Integer from 1 to 65535. | `5432` |
| `postgresql_databases` | Databases created and maintained by the role. | List of dictionaries (name, owner, encoding). | `[]` |
| `postgresql_db_users` | Login roles created and maintained by the role. | List of dictionaries (name, password_var, privileges). | `[]` |
| `postgresql_hba_entries` | Lines added to pg_hba.conf on top of the default local rules. | List of five-field strings "type database user address method", for instance 'host all all 10.0.0.0/8 scram-sha-256'. | `[]` |
| `postgresql_max_connections` | Value of max_connections in postgresql.conf. | Positive integer. | `100` |

## Internal variables

Defined in `vars/main.yml`, they are not meant to be overridden.

- `postgresql_config_dir`: directory of postgresql.conf and pg_hba.conf, per OS family
- `postgresql_settings`: parameters applied to the server, built from the options
- `postgresql_users_with_password`: roles that have a password variable filled in

## Handlers

- `Reload PostgreSQL`
- `Restart PostgreSQL`

## Required collections

- `community.postgresql` — accepted versions: `>=3.13.0,<6.0.0`

These ranges are the ones of `requirements.yml`, at the root of the Ansible
project; that file is the one that counts at install time.

## Usage example

```yaml
- name: Apply the postgresql role
  hosts: dbservers
  become: true
  roles:
    - role: postgresql
```

## Supported systems

- Debian
- Ubuntu
