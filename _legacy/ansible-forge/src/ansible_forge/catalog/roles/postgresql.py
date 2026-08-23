"""Définition du rôle ``postgresql`` : serveur PostgreSQL, bases et comptes."""

from __future__ import annotations

from ansible_forge.catalog.definition import OptionKind, RoleDefinition, RoleOption

DATABASE_FIELDS = (
    RoleOption(
        name="name",
        question="Nom de la base",
        description="Nom de la base de données créée.",
        allowed="Identifiant PostgreSQL valide, 1 à 63 caractères.",
        default="",
        kind=OptionKind.TEXT,
    ),
    RoleOption(
        name="owner",
        question="Propriétaire de la base",
        description="Rôle PostgreSQL propriétaire de la base.",
        allowed="Nom d'un rôle déclaré dans l'option 'db_users'.",
        default="",
        kind=OptionKind.TEXT,
    ),
    RoleOption(
        name="encoding",
        question="Encodage de la base",
        description="Encodage utilisé à la création de la base.",
        allowed="Encodage PostgreSQL, par exemple 'UTF8'.",
        default="UTF8",
        kind=OptionKind.TEXT,
    ),
)

DB_USER_FIELDS = (
    RoleOption(
        name="name",
        question="Nom du rôle PostgreSQL",
        description="Nom du rôle de connexion créé.",
        allowed="Identifiant PostgreSQL valide, 1 à 63 caractères.",
        default="",
        kind=OptionKind.TEXT,
    ),
    RoleOption(
        name="password_var",
        question="Nom de la variable contenant le mot de passe",
        description="Variable Ansible (à placer dans le vault) portant le mot de passe.",
        allowed="Nom de variable Ansible, par exemple 'vault_pg_app_password'.",
        default="",
        kind=OptionKind.TEXT,
    ),
    RoleOption(
        name="privileges",
        question="Privilèges à accorder (format module postgresql_user)",
        description="Privilèges accordés au rôle sur ses objets.",
        allowed="Chaîne au format 'db:ALL' ou vide.",
        default="",
        kind=OptionKind.TEXT,
    ),
)

ROLE = RoleDefinition(
    name="postgresql",
    summary="Serveur PostgreSQL : installation, écoute réseau, bases, rôles et règles pg_hba.",
    collections=("community.postgresql",),
    handlers=("Recharger PostgreSQL", "Redémarrer PostgreSQL"),
    tags=("postgresql", "database"),
    options=(
        RoleOption(
            name="version",
            question="Version majeure de PostgreSQL",
            description="Version majeure installée depuis les dépôts de la distribution.",
            allowed="Numéro de version majeure, par exemple '15' ou '16'.",
            default="16",
            kind=OptionKind.TEXT,
        ),
        RoleOption(
            name="listen_addresses",
            question="Adresses d'écoute du serveur",
            description="Valeur de listen_addresses dans postgresql.conf.",
            allowed="'localhost', '*' ou une liste d'adresses séparées par des virgules.",
            default="localhost",
            kind=OptionKind.TEXT,
        ),
        RoleOption(
            name="port",
            question="Port d'écoute PostgreSQL",
            description="Port TCP du serveur PostgreSQL.",
            allowed="Entier de 1 à 65535.",
            default=5432,
            kind=OptionKind.INT,
        ),
        RoleOption(
            name="databases",
            question="Bases de données à créer",
            description="Bases créées et maintenues par le rôle.",
            allowed="Liste de dictionnaires (name, owner, encoding).",
            default=[],
            kind=OptionKind.RECORDS,
            fields=DATABASE_FIELDS,
        ),
        RoleOption(
            name="db_users",
            question="Rôles PostgreSQL à créer",
            description="Rôles de connexion créés et maintenus par le rôle.",
            allowed="Liste de dictionnaires (name, password_var, privileges).",
            default=[],
            kind=OptionKind.RECORDS,
            fields=DB_USER_FIELDS,
        ),
        RoleOption(
            name="hba_entries",
            question="Règles pg_hba supplémentaires (format 'type database user address method')",
            description="Lignes ajoutées à pg_hba.conf en plus des règles locales par défaut.",
            allowed=(
                "Liste de chaînes à cinq champs « type base utilisateur adresse méthode », "
                "par exemple 'host all all 10.0.0.0/8 scram-sha-256'."
            ),
            default=[],
            kind=OptionKind.LIST,
        ),
        RoleOption(
            name="max_connections",
            question="Nombre maximal de connexions simultanées",
            description="Valeur de max_connections dans postgresql.conf.",
            allowed="Entier positif.",
            default=100,
            kind=OptionKind.INT,
        ),
    ),
)
