# Rôle `postgresql`

Serveur PostgreSQL : installation, écoute réseau, bases, rôles et règles pg_hba.

## Variables

Toutes les variables sont définies dans `defaults/main.yml` et peuvent être
surchargées depuis `group_vars/` ou `host_vars/`.

| Variable | Rôle | Valeurs admises | Défaut |
|---|---|---|---|
| `postgresql_version` | Version majeure installée depuis les dépôts de la distribution. | Numéro de version majeure, par exemple '15' ou '16'. | `'16'` |
| `postgresql_listen_addresses` | Valeur de listen_addresses dans postgresql.conf. | 'localhost', '*' ou une liste d'adresses séparées par des virgules. | `localhost` |
| `postgresql_port` | Port TCP du serveur PostgreSQL. | Entier de 1 à 65535. | `5432` |
| `postgresql_databases` | Bases créées et maintenues par le rôle. | Liste de dictionnaires (name, owner, encoding). | `[]` |
| `postgresql_db_users` | Rôles de connexion créés et maintenus par le rôle. | Liste de dictionnaires (name, password_var, privileges). | `[]` |
| `postgresql_hba_entries` | Lignes ajoutées à pg_hba.conf en plus des règles locales par défaut. | Liste de chaînes à cinq champs « type base utilisateur adresse méthode », par exemple 'host all all 10.0.0.0/8 scram-sha-256'. | `[]` |
| `postgresql_max_connections` | Valeur de max_connections dans postgresql.conf. | Entier positif. | `100` |

## Variables internes

Définies dans `vars/main.yml`, elles ne sont pas destinées à être surchargées.

- `postgresql_config_dir` : répertoire de postgresql.conf et pg_hba.conf, selon la famille d'OS
- `postgresql_settings` : paramètres appliqués au serveur, construits depuis les options
- `postgresql_users_with_password` : rôles disposant d'une variable de mot de passe renseignée

## Handlers

- `Recharger PostgreSQL`
- `Redémarrer PostgreSQL`

## Collections requises

- `community.postgresql`

## Exemple d'utilisation

```yaml
- name: Appliquer le rôle postgresql
  hosts: dbservers
  become: true
  roles:
    - role: postgresql
```

## Systèmes supportés

- Debian
- Ubuntu
