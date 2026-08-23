# Rôle `docker`

Moteur Docker CE : dépôt officiel, service, plugin Compose et options du démon.

## Variables

Toutes les variables sont définies dans `defaults/main.yml` et peuvent être
surchargées depuis `group_vars/` ou `host_vars/`.

| Variable | Rôle | Valeurs admises | Défaut |
|---|---|---|---|
| `docker_channel` | Canal du dépôt officiel Docker utilisé pour l'installation. | stable ou test. | `stable` |
| `docker_install_compose_plugin` | Installe le paquet docker-compose-plugin. | true ou false. | `true` |
| `docker_users_in_docker_group` | Comptes locaux autorisés à piloter Docker sans sudo. | Liste de noms de comptes existants sur la machine. | `[]` |
| `docker_log_driver` | Valeur de log-driver dans /etc/docker/daemon.json. | json-file, local, journald ou syslog. | `json-file` |
| `docker_log_max_size` | Valeur de log-opts.max-size dans /etc/docker/daemon.json. | Taille Docker, par exemple '10m' ou '100m'. | `10m` |
| `docker_log_max_file` | Valeur de log-opts.max-file dans /etc/docker/daemon.json. | Entier positif. | `3` |
| `docker_service_enabled` | Active et démarre le service docker. | true ou false. | `true` |

## Variables internes

Définies dans `vars/main.yml`, elles ne sont pas destinées à être surchargées.

- `docker_apt_arch` : architecture APT déduite de l'architecture de la machine
- `docker_packages` : liste finale des paquets, plugin Compose inclus si demandé

## Handlers

- `Redémarrer Docker`

## Exemple d'utilisation

```yaml
- name: Appliquer le rôle docker
  hosts: webservers
  become: true
  roles:
    - role: docker
```

## Systèmes supportés

- Debian
- Ubuntu
