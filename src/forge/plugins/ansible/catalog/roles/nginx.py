"""Definition of the ``nginx`` role: web server and main virtual host."""

from __future__ import annotations

from forge.plugins.ansible.catalog.definition import OptionKind, RoleDefinition, RoleOption

ROLE = RoleDefinition(
    name="nginx",
    summary="nginx web server: installation, global settings and main virtual host.",
    collections=(),
    handlers=("Reload nginx", "Restart nginx"),
    tags=("nginx", "web"),
    options=(
        RoleOption(
            name="server_name",
            question="Domain name served (server_name)",
            description="Domain name of the main virtual host.",
            allowed="Valid domain name, for instance 'www.example.com'.",
            default="example.local",
            kind=OptionKind.TEXT,
        ),
        RoleOption(
            name="document_root",
            question="Document root",
            description="Directory served by the main virtual host.",
            allowed="Absolute path, created by the role if it does not exist.",
            default="/var/www/html",
            kind=OptionKind.TEXT,
        ),
        RoleOption(
            name="listen_port",
            question="HTTP listening port",
            description="Cleartext TCP port of the virtual host.",
            allowed="Integer from 1 to 65535.",
            default=80,
            kind=OptionKind.INT,
        ),
        RoleOption(
            name="enable_https",
            question="Enable HTTPS?",
            description="Adds a TLS server block and the HTTP to HTTPS redirection.",
            allowed="true or false.",
            default=False,
            kind=OptionKind.BOOL,
        ),
        RoleOption(
            name="ssl_certificate",
            question="Path of the TLS certificate on the target machine",
            description="Certificate used when enable_https is true.",
            allowed="Absolute path to a PEM certificate already present on the target.",
            default="/etc/ssl/certs/ssl-cert-snakeoil.pem",
            kind=OptionKind.TEXT,
        ),
        RoleOption(
            name="ssl_certificate_key",
            question="Path of the TLS private key on the target machine",
            description="Private key used when enable_https is true.",
            allowed="Absolute path to a PEM key already present on the target.",
            default="/etc/ssl/private/ssl-cert-snakeoil.key",
            kind=OptionKind.TEXT,
        ),
        RoleOption(
            name="remove_default_site",
            question="Remove the default site of the distribution?",
            description="Disables the 'default' vhost shipped by the nginx package.",
            allowed="true or false.",
            default=True,
            kind=OptionKind.BOOL,
        ),
        RoleOption(
            name="worker_processes",
            question="Number of worker processes",
            description="Value of the worker_processes directive.",
            allowed="'auto' or a positive integer.",
            default="auto",
            kind=OptionKind.TEXT,
        ),
        RoleOption(
            name="client_max_body_size",
            question="Maximum size of the request bodies",
            description="Value of the client_max_body_size directive.",
            allowed="An nginx size, for instance '1m', '20m' or '1g'.",
            default="1m",
            kind=OptionKind.TEXT,
        ),
    ),
)
