# Rôle `firewall`

Pare-feu local : ufw (Debian) ou firewalld (RedHat), politique par défaut et ports ouverts.

## Variables

Toutes les variables sont définies dans `defaults/main.yml` et peuvent être
surchargées depuis `group_vars/` ou `host_vars/`.

| Variable | Rôle | Valeurs admises | Défaut |
|---|---|---|---|
| `firewall_backend` | Backend utilisé ; 'auto' choisit ufw sur Debian et firewalld sur RedHat. | auto, ufw ou firewalld. | `auto` |
| `firewall_default_incoming_policy` | Action appliquée au trafic entrant non explicitement autorisé. | deny, reject ou allow. | `deny` |
| `firewall_default_outgoing_policy` | Action appliquée au trafic sortant non explicitement autorisé. | allow, deny ou reject. | `allow` |
| `firewall_allowed_tcp_ports` | Ports TCP ouverts en entrée. | Liste d'entiers de 1 à 65535. | `_:
  - 22
  - 80
  - 443` |
| `firewall_allowed_udp_ports` | Ports UDP ouverts en entrée. | Liste d'entiers de 1 à 65535. | `[]` |
| `firewall_enabled` | Active et démarre le service de pare-feu. | true ou false. | `true` |
| `firewall_log_level` | Verbosité des journaux du pare-feu. | off, low, medium, high ou full. | `low` |

## Variables internes

Définies dans `vars/main.yml`, elles ne sont pas destinées à être surchargées.

- `firewall_effective_backend` : backend réellement utilisé, une fois « auto » résolu
- `firewall_zone` : zone firewalld dans laquelle les règles sont posées
- `firewall_zone_target` : cible de zone firewalld déduite de la politique par défaut

## Handlers

- `Recharger le pare-feu`

## Collections requises

- `community.general`
- `ansible.posix`

## Exemple d'utilisation

```yaml
- name: Appliquer le rôle firewall
  hosts: webservers
  become: true
  roles:
    - role: firewall
```

## Systèmes supportés

- Debian
- Ubuntu
