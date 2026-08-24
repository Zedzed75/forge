"""Définition du rôle ``firewall`` : filtrage réseau via ufw ou firewalld."""

from __future__ import annotations

from forge.plugins.ansible.catalog.definition import OptionKind, RoleDefinition, RoleOption

ROLE = RoleDefinition(
    name="firewall",
    summary="Pare-feu local : ufw (Debian) ou firewalld (RedHat), politique par défaut et ports ouverts.",
    collections=("community.general", "ansible.posix"),
    handlers=("Recharger le pare-feu",),
    tags=("firewall", "security"),
    options=(
        RoleOption(
            name="backend",
            question="Implémentation de pare-feu",
            description="Backend utilisé ; 'auto' choisit ufw sur Debian et firewalld sur RedHat.",
            allowed="auto, ufw ou firewalld.",
            default="auto",
            kind=OptionKind.CHOICE,
            choices=("auto", "ufw", "firewalld"),
        ),
        RoleOption(
            name="default_incoming_policy",
            question="Politique par défaut pour le trafic entrant",
            description="Action appliquée au trafic entrant non explicitement autorisé.",
            allowed="deny, reject ou allow.",
            default="deny",
            kind=OptionKind.CHOICE,
            choices=("deny", "reject", "allow"),
        ),
        RoleOption(
            name="default_outgoing_policy",
            question="Politique par défaut pour le trafic sortant",
            description="Action appliquée au trafic sortant non explicitement autorisé.",
            allowed="allow, deny ou reject.",
            default="allow",
            kind=OptionKind.CHOICE,
            choices=("allow", "deny", "reject"),
        ),
        RoleOption(
            name="allowed_tcp_ports",
            question="Ports TCP autorisés (séparés par des virgules)",
            description="Ports TCP ouverts en entrée.",
            allowed="Liste d'entiers de 1 à 65535.",
            default=[22, 80, 443],
            kind=OptionKind.LIST,
            item_kind=OptionKind.INT,
        ),
        RoleOption(
            name="allowed_udp_ports",
            question="Ports UDP autorisés (séparés par des virgules)",
            description="Ports UDP ouverts en entrée.",
            allowed="Liste d'entiers de 1 à 65535.",
            default=[],
            kind=OptionKind.LIST,
            item_kind=OptionKind.INT,
        ),
        RoleOption(
            name="enabled",
            question="Activer le pare-feu au démarrage ?",
            description="Active et démarre le service de pare-feu.",
            allowed="true ou false.",
            default=True,
            kind=OptionKind.BOOL,
        ),
        RoleOption(
            name="log_level",
            question="Niveau de journalisation du pare-feu",
            description="Verbosité des journaux du pare-feu.",
            allowed="off, low, medium, high ou full.",
            default="low",
            kind=OptionKind.CHOICE,
            choices=("off", "low", "medium", "high", "full"),
        ),
    ),
)
