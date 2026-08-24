# Rôle `nginx`

Serveur web nginx : installation, réglages globaux et hôte virtuel principal.

## Variables

Toutes les variables sont définies dans `defaults/main.yml` et peuvent être
surchargées depuis `group_vars/` ou `host_vars/`.

| Variable | Rôle | Valeurs admises | Défaut |
|---|---|---|---|
| `nginx_server_name` | Nom de domaine de l'hôte virtuel principal. | Nom de domaine valide, par exemple 'www.example.com'. | `example.local` |
| `nginx_document_root` | Répertoire servi par l'hôte virtuel principal. | Chemin absolu, créé par le rôle s'il n'existe pas. | `/var/www/html` |
| `nginx_listen_port` | Port TCP en clair de l'hôte virtuel. | Entier de 1 à 65535. | `80` |
| `nginx_enable_https` | Ajoute un bloc server TLS et la redirection HTTP vers HTTPS. | true ou false. | `false` |
| `nginx_ssl_certificate` | Certificat utilisé lorsque enable_https vaut true. | Chemin absolu vers un certificat PEM déjà présent sur la cible. | `/etc/ssl/certs/ssl-cert-snakeoil.pem` |
| `nginx_ssl_certificate_key` | Clé privée utilisée lorsque enable_https vaut true. | Chemin absolu vers une clé PEM déjà présente sur la cible. | `/etc/ssl/private/ssl-cert-snakeoil.key` |
| `nginx_remove_default_site` | Désactive le vhost 'default' livré par le paquet nginx. | true ou false. | `true` |
| `nginx_worker_processes` | Valeur de la directive worker_processes. | 'auto' ou un entier positif. | `auto` |
| `nginx_client_max_body_size` | Valeur de la directive client_max_body_size. | Taille nginx, par exemple '1m', '20m' ou '1g'. | `1m` |

## Variables internes

Définies dans `vars/main.yml`, elles ne sont pas destinées à être surchargées.

- `nginx_user` : compte système des workers, résolu selon la famille d'OS
- `nginx_config_dir` : répertoire de configuration de nginx
- `nginx_default_site_path` : site par défaut de la distribution, vide si absent

## Handlers

- `Recharger nginx`
- `Redémarrer nginx`

## Exemple d'utilisation

```yaml
- name: Appliquer le rôle nginx
  hosts: webservers
  become: true
  roles:
    - role: nginx
```

## Systèmes supportés

- Debian
- Ubuntu
