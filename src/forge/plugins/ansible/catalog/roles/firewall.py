"""Definition of the ``firewall`` role: network filtering via ufw or firewalld."""

from __future__ import annotations

from forge.plugins.ansible.catalog.definition import OptionKind, RoleDefinition, RoleOption

ROLE = RoleDefinition(
    name="firewall",
    summary="Local firewall: ufw (Debian) or firewalld (RedHat), default policy and open ports.",
    collections=("community.general", "ansible.posix"),
    handlers=("Reload the firewall",),
    tags=("firewall", "security"),
    options=(
        RoleOption(
            name="backend",
            question="Firewall implementation",
            description="Backend used; 'auto' picks ufw on Debian and firewalld on RedHat.",
            allowed="auto, ufw or firewalld.",
            default="auto",
            kind=OptionKind.CHOICE,
            choices=("auto", "ufw", "firewalld"),
        ),
        RoleOption(
            name="default_incoming_policy",
            question="Default policy for incoming traffic",
            description="Action applied to incoming traffic that is not explicitly allowed.",
            allowed="deny, reject or allow.",
            default="deny",
            kind=OptionKind.CHOICE,
            choices=("deny", "reject", "allow"),
        ),
        RoleOption(
            name="default_outgoing_policy",
            question="Default policy for outgoing traffic",
            description="Action applied to outgoing traffic that is not explicitly allowed.",
            allowed="allow, deny or reject.",
            default="allow",
            kind=OptionKind.CHOICE,
            choices=("allow", "deny", "reject"),
        ),
        RoleOption(
            name="allowed_tcp_ports",
            question="Allowed TCP ports (comma-separated)",
            description="TCP ports opened for inbound traffic.",
            allowed="List of integers from 1 to 65535.",
            default=[22, 80, 443],
            kind=OptionKind.LIST,
            item_kind=OptionKind.INT,
        ),
        RoleOption(
            name="allowed_udp_ports",
            question="Allowed UDP ports (comma-separated)",
            description="UDP ports opened for inbound traffic.",
            allowed="List of integers from 1 to 65535.",
            default=[],
            kind=OptionKind.LIST,
            item_kind=OptionKind.INT,
        ),
        RoleOption(
            name="enabled",
            question="Enable the firewall at boot?",
            description="Enables and starts the firewall service.",
            allowed="true or false.",
            default=True,
            kind=OptionKind.BOOL,
        ),
        RoleOption(
            name="log_level",
            question="Logging level of the firewall",
            description="Verbosity of the firewall logs.",
            allowed="off, low, medium, high or full.",
            default="low",
            kind=OptionKind.CHOICE,
            choices=("off", "low", "medium", "high", "full"),
        ),
    ),
)
