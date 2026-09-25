"""Definition of the ``postgresql`` role: PostgreSQL server, databases and accounts."""

from __future__ import annotations

from forge.plugins.ansible.catalog.definition import OptionKind, RoleDefinition, RoleOption

DATABASE_FIELDS = (
    RoleOption(
        name="name",
        question="Name of the database",
        description="Name of the database created.",
        allowed="Valid PostgreSQL identifier, 1 to 63 characters.",
        default="",
        kind=OptionKind.TEXT,
    ),
    RoleOption(
        name="owner",
        question="Owner of the database",
        description="PostgreSQL role owning the database.",
        allowed="Name of a role declared in the 'db_users' option.",
        default="",
        kind=OptionKind.TEXT,
    ),
    RoleOption(
        name="encoding",
        question="Encoding of the database",
        description="Encoding used when the database is created.",
        allowed="A PostgreSQL encoding, for instance 'UTF8'.",
        default="UTF8",
        kind=OptionKind.TEXT,
    ),
)

DB_USER_FIELDS = (
    RoleOption(
        name="name",
        question="Name of the PostgreSQL role",
        description="Name of the login role created.",
        allowed="Valid PostgreSQL identifier, 1 to 63 characters.",
        default="",
        kind=OptionKind.TEXT,
    ),
    RoleOption(
        name="password_var",
        question="Name of the variable holding the password",
        description="Ansible variable (to be placed in the vault) carrying the password.",
        allowed="An Ansible variable name, for instance 'vault_pg_app_password'.",
        default="",
        kind=OptionKind.TEXT,
    ),
    RoleOption(
        name="privileges",
        question="Privileges to grant (postgresql_user module format)",
        description="Privileges granted to the role on its objects.",
        allowed="String in the 'db:ALL' format, or empty.",
        default="",
        kind=OptionKind.TEXT,
    ),
)

ROLE = RoleDefinition(
    name="postgresql",
    summary="PostgreSQL server: installation, network listening, databases, roles and pg_hba rules.",
    collections=("community.postgresql",),
    handlers=("Reload PostgreSQL", "Restart PostgreSQL"),
    tags=("postgresql", "database"),
    options=(
        RoleOption(
            name="version",
            question="Major version of PostgreSQL",
            description="Major version installed from the repositories of the distribution.",
            allowed="Major version number, for instance '15' or '16'.",
            default="16",
            kind=OptionKind.TEXT,
        ),
        RoleOption(
            name="listen_addresses",
            question="Listening addresses of the server",
            description="Value of listen_addresses in postgresql.conf.",
            allowed="'localhost', '*' or a comma-separated list of addresses.",
            default="localhost",
            kind=OptionKind.TEXT,
        ),
        RoleOption(
            name="port",
            question="PostgreSQL listening port",
            description="TCP port of the PostgreSQL server.",
            allowed="Integer from 1 to 65535.",
            default=5432,
            kind=OptionKind.INT,
        ),
        RoleOption(
            name="databases",
            question="Databases to create",
            description="Databases created and maintained by the role.",
            allowed="List of dictionaries (name, owner, encoding).",
            default=[],
            kind=OptionKind.RECORDS,
            fields=DATABASE_FIELDS,
        ),
        RoleOption(
            name="db_users",
            question="PostgreSQL roles to create",
            description="Login roles created and maintained by the role.",
            allowed="List of dictionaries (name, password_var, privileges).",
            default=[],
            kind=OptionKind.RECORDS,
            fields=DB_USER_FIELDS,
        ),
        RoleOption(
            name="hba_entries",
            question="Additional pg_hba rules (format 'type database user address method')",
            description="Lines added to pg_hba.conf on top of the default local rules.",
            allowed=(
                "List of five-field strings \"type database user address method\", "
                "for instance 'host all all 10.0.0.0/8 scram-sha-256'."
            ),
            default=[],
            kind=OptionKind.LIST,
        ),
        RoleOption(
            name="max_connections",
            question="Maximum number of simultaneous connections",
            description="Value of max_connections in postgresql.conf.",
            allowed="Positive integer.",
            default=100,
            kind=OptionKind.INT,
        ),
    ),
)
