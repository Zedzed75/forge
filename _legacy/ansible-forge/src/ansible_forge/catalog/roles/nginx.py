"""Définition du rôle ``nginx`` : serveur web et hôte virtuel principal."""

from __future__ import annotations

from ansible_forge.catalog.definition import OptionKind, RoleDefinition, RoleOption

ROLE = RoleDefinition(
    name="nginx",
    summary="Serveur web nginx : installation, réglages globaux et hôte virtuel principal.",
    collections=(),
    handlers=("Recharger nginx", "Redémarrer nginx"),
    tags=("nginx", "web"),
    options=(
        RoleOption(
            name="server_name",
            question="Nom de domaine servi (server_name)",
            description="Nom de domaine de l'hôte virtuel principal.",
            allowed="Nom de domaine valide, par exemple 'www.example.com'.",
            default="example.local",
            kind=OptionKind.TEXT,
        ),
        RoleOption(
            name="document_root",
            question="Racine des documents",
            description="Répertoire servi par l'hôte virtuel principal.",
            allowed="Chemin absolu, créé par le rôle s'il n'existe pas.",
            default="/var/www/html",
            kind=OptionKind.TEXT,
        ),
        RoleOption(
            name="listen_port",
            question="Port HTTP d'écoute",
            description="Port TCP en clair de l'hôte virtuel.",
            allowed="Entier de 1 à 65535.",
            default=80,
            kind=OptionKind.INT,
        ),
        RoleOption(
            name="enable_https",
            question="Activer HTTPS ?",
            description="Ajoute un bloc server TLS et la redirection HTTP vers HTTPS.",
            allowed="true ou false.",
            default=False,
            kind=OptionKind.BOOL,
        ),
        RoleOption(
            name="ssl_certificate",
            question="Chemin du certificat TLS sur la machine cible",
            description="Certificat utilisé lorsque enable_https vaut true.",
            allowed="Chemin absolu vers un certificat PEM déjà présent sur la cible.",
            default="/etc/ssl/certs/ssl-cert-snakeoil.pem",
            kind=OptionKind.TEXT,
        ),
        RoleOption(
            name="ssl_certificate_key",
            question="Chemin de la clé privée TLS sur la machine cible",
            description="Clé privée utilisée lorsque enable_https vaut true.",
            allowed="Chemin absolu vers une clé PEM déjà présente sur la cible.",
            default="/etc/ssl/private/ssl-cert-snakeoil.key",
            kind=OptionKind.TEXT,
        ),
        RoleOption(
            name="remove_default_site",
            question="Supprimer le site par défaut de la distribution ?",
            description="Désactive le vhost 'default' livré par le paquet nginx.",
            allowed="true ou false.",
            default=True,
            kind=OptionKind.BOOL,
        ),
        RoleOption(
            name="worker_processes",
            question="Nombre de processus worker",
            description="Valeur de la directive worker_processes.",
            allowed="'auto' ou un entier positif.",
            default="auto",
            kind=OptionKind.TEXT,
        ),
        RoleOption(
            name="client_max_body_size",
            question="Taille maximale du corps des requêtes",
            description="Valeur de la directive client_max_body_size.",
            allowed="Taille nginx, par exemple '1m', '20m' ou '1g'.",
            default="1m",
            kind=OptionKind.TEXT,
        ),
    ),
)
