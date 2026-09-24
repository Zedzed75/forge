# Rôle `common`

Socle système : paquets de base, fuseau horaire, synchronisation NTP, bannière MOTD.

## Variables

Toutes les variables sont définies dans `defaults/main.yml` et peuvent être
surchargées depuis `group_vars/` ou `host_vars/`.

| Variable | Rôle | Valeurs admises | Défaut |
|---|---|---|---|
| `common_timezone` | Fuseau horaire appliqué à toutes les machines du groupe. | Identifiant de la base tz, par exemple 'Europe/Paris' ou 'UTC'. | `Europe/Paris` |
| `common_packages` | Paquets installés sur toutes les machines du groupe. | Liste de noms de paquets valides pour la famille d'OS ciblée. | `_:
  - ca-certificates
  - curl
  - htop
  - vim` |
| `common_manage_timezone` | Active la configuration du fuseau horaire par le rôle. | true ou false. | `true` |
| `common_enable_ntp` | Installe et active la synchronisation horaire (systemd-timesyncd). | true ou false. | `true` |
| `common_manage_motd` | Déploie un fichier /etc/motd décrivant le rôle de la machine. | true ou false. | `true` |

## Variables internes

Définies dans `vars/main.yml`, elles ne sont pas destinées à être surchargées.

- `common_ntp_package` : paquet de synchronisation horaire résolu selon la famille d'OS
- `common_ntp_service` : service de synchronisation horaire résolu selon la famille d'OS

## Handlers

- `Redémarrer le service de synchronisation horaire`

## Collections requises

- `community.general` — versions acceptées : `>=13.4.0,<14.0.0`

Ces intervalles sont ceux de `requirements.yml`, à la racine du projet Ansible ;
c'est ce fichier qui fait foi à l'installation.

## Exemple d'utilisation

```yaml
- name: Appliquer le rôle common
  hosts: gateways
  become: true
  roles:
    - role: common
```

## Systèmes supportés

- Debian
- Ubuntu
