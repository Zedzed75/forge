"""Modèle de specification d'un projet Ansible à générer.

``ProjectSpec`` décrit entièrement le projet cible : identité, paramètres de
connexion, environnements, groupes d'hôtes, hôtes, rôles sélectionnés et options
de génération. C'est la seule entrée du moteur de rendu : même spec => même
sortie, octet pour octet.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ansible_forge.catalog.registry import get_role, role_names, sort_roles, validate_options
from ansible_forge.errors import CatalogError
from ansible_forge.models.enums import OSFamily
from ansible_forge.validation import (
    ENV_NAME_RE,
    GROUP_NAME_RE,
    HOST_NAME_RE,
    PROJECT_NAME_RE,
    RESERVED_GROUP_NAMES,
    USER_NAME_RE,
    VAR_NAME_RE,
    check_host_address,
    check_pattern,
    find_duplicates,
)

#: Version du format de ``forge.yml``. Incrémentée à chaque rupture de format.
SPEC_VERSION = 1


class ForgeModel(BaseModel):
    """Classe de base : interdit les champs inconnus pour détecter les fautes de frappe."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


def _check_var_names(values: dict[str, Any], context: str) -> dict[str, Any]:
    """Valide les noms de variables d'un dictionnaire libre."""
    for key in values:
        error = check_pattern(
            key,
            VAR_NAME_RE,
            f"Nom de variable ({context})",
            "Attendu : minuscules, chiffres et '_', commençant par une lettre ou '_'.",
        )
        if error:
            raise ValueError(error)
    return dict(values)


class HostSpec(ForgeModel):
    """Une machine cible dans un environnement donné."""

    #: Nom d'inventaire, utilisé comme nom de fichier host_vars.
    name: str
    #: Adresse de connexion : IP ou nom de domaine.
    ansible_host: str
    #: Port SSH spécifique ; ``None`` = hérite du paramètre global du projet.
    ansible_port: int | None = None
    #: Compte SSH spécifique ; ``None`` = hérite du paramètre global du projet.
    ansible_user: str | None = None
    #: Variables propres à cet hôte, écrites dans ``host_vars/<name>.yml``.
    vars: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        error = check_pattern(
            value,
            HOST_NAME_RE,
            "Nom d'hôte",
            "Attendu : minuscules, chiffres, '.', '-' et '_', 1 à 63 caractères.",
        )
        if error:
            raise ValueError(error)
        return value

    @field_validator("ansible_host")
    @classmethod
    def _validate_address(cls, value: str) -> str:
        error = check_host_address(value)
        if error:
            raise ValueError(error)
        return value

    @field_validator("ansible_port")
    @classmethod
    def _validate_port(cls, value: int | None) -> int | None:
        if value is None:
            return None
        if not 1 <= value <= 65535:
            raise ValueError(f"Le port doit être compris entre 1 et 65535, reçu : {value}.")
        return value

    @field_validator("ansible_user")
    @classmethod
    def _validate_user(cls, value: str | None) -> str | None:
        if value is None:
            return None
        error = check_pattern(
            value, USER_NAME_RE, "Nom d'utilisateur SSH", "Attendu : un nom de compte POSIX."
        )
        if error:
            raise ValueError(error)
        return value

    @field_validator("vars")
    @classmethod
    def _validate_vars(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _check_var_names(value, "host_vars")


class GroupSpec(ForgeModel):
    """Un groupe d'hôtes, défini au niveau du projet et peuplé par environnement."""

    #: Nom du groupe Ansible (sans tiret : contrainte des noms de groupes).
    name: str
    #: Description métier, reprise en commentaire dans l'inventaire et les vars.
    description: str = ""
    #: Rôles appliqués à ce groupe, dans l'ordre du catalogue.
    roles: list[str] = Field(default_factory=lambda: ["common"])
    #: Variables du groupe, écrites dans ``group_vars/<name>.yml``.
    vars: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        error = check_pattern(
            value,
            GROUP_NAME_RE,
            "Nom de groupe",
            "Attendu : minuscules, chiffres et '_' (le tiret est interdit dans un nom de groupe).",
        )
        if error:
            raise ValueError(error)
        if value in RESERVED_GROUP_NAMES:
            reserved = ", ".join(sorted(RESERVED_GROUP_NAMES))
            raise ValueError(f"Le nom de groupe '{value}' est réservé par Ansible ({reserved}).")
        return value

    @field_validator("roles")
    @classmethod
    def _validate_roles(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("Un groupe doit appliquer au moins un rôle.")
        duplicates = find_duplicates(value)
        if duplicates:
            raise ValueError(f"Rôle(s) en double dans le groupe : {', '.join(duplicates)}.")
        for name in value:
            try:
                get_role(name)
            except CatalogError as exc:
                raise ValueError(str(exc)) from None
        return sort_roles(value)

    @field_validator("vars")
    @classmethod
    def _validate_vars(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _check_var_names(value, "group_vars")


class EnvironmentSpec(ForgeModel):
    """Un environnement (dev, staging, prod...) et les hôtes qu'il contient."""

    #: Nom de l'environnement, utilisé comme nom de répertoire d'inventaire.
    name: str
    #: Hôtes de l'environnement, indexés par nom de groupe.
    hosts: dict[str, list[HostSpec]] = Field(default_factory=dict)
    #: Surcharges de variables propres à l'environnement, indexées par groupe
    #: ('all' pour toutes les machines de l'environnement).
    group_vars: dict[str, dict[str, Any]] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        error = check_pattern(
            value,
            ENV_NAME_RE,
            "Nom d'environnement",
            "Attendu : minuscules, chiffres et '_', 1 à 32 caractères.",
        )
        if error:
            raise ValueError(error)
        return value

    @model_validator(mode="after")
    def _validate_host_uniqueness(self) -> "EnvironmentSpec":
        names = [host.name for hosts in self.hosts.values() for host in hosts]
        duplicates = find_duplicates(names)
        if duplicates:
            raise ValueError(
                f"Hôte(s) déclaré(s) plusieurs fois dans l'environnement "
                f"'{self.name}' : {', '.join(duplicates)}."
            )
        for scope, values in self.group_vars.items():
            _check_var_names(values, f"inventories/{self.name}/group_vars/{scope}")
        return self

    def all_hosts(self) -> list[HostSpec]:
        """Retourne tous les hôtes de l'environnement, triés par nom (rendu déterministe)."""
        hosts = [host for group in sorted(self.hosts) for host in self.hosts[group]]
        return sorted(hosts, key=lambda host: host.name)


class RoleConfig(ForgeModel):
    """Les réponses de l'utilisateur aux questions d'un rôle du catalogue."""

    #: Nom du rôle, présent au catalogue.
    name: str
    #: Valeurs des options du rôle ; complétées par les défauts du catalogue.
    options: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _resolve_against_catalog(cls, data: Any) -> Any:
        """Complète les options manquantes avec les défauts du catalogue.

        Effectué en mode ``before`` afin que le modèle construit soit déjà
        normalisé : un ``forge.yml`` partiel et un ``forge.yml`` complet
        produisent le même objet, donc la même sortie.
        """
        if not isinstance(data, dict) or "name" not in data:
            return data
        try:
            get_role(data["name"])
            options = validate_options(data["name"], data.get("options") or {})
        except CatalogError as exc:
            raise ValueError(str(exc)) from None
        return {**data, "options": options}


class GenerationOptions(ForgeModel):
    """Options influant sur les fichiers annexes produits par le générateur."""

    #: Génère les modèles de fichiers vault et la documentation associée.
    use_vault: bool = True
    #: Génère .gitignore, .yamllint et .ansible-lint.
    write_lint_config: bool = True
    #: Copie forge.yml dans le projet généré (rejouabilité).
    embed_spec: bool = True
    #: Génère un workflow CI exécutant ansible-lint et --syntax-check.
    write_ci: bool = False


class ProjectSpec(ForgeModel):
    """Spécification complète d'un projet Ansible à générer."""

    #: Version du format de fichier ``forge.yml``.
    spec_version: int = SPEC_VERSION
    #: Nom du projet, utilisé dans les en-têtes et la documentation générée.
    project_name: str
    #: Description courte du projet.
    description: str = ""
    #: Auteur ou équipe responsable du projet.
    author: str = ""
    #: Famille d'OS ciblée : détermine paquets et backend pare-feu.
    os_family: OSFamily = OSFamily.DEBIAN
    #: Compte SSH utilisé par défaut pour se connecter aux machines.
    remote_user: str = "ansible"
    #: Active l'escalade de privilèges (become) dans les playbooks générés.
    become: bool = True
    #: Port SSH utilisé par défaut.
    ssh_port: int = 22
    #: Interpréteur Python distant déclaré dans les inventaires.
    python_interpreter: str = "auto_silent"
    #: Environnements du projet, au moins un.
    environments: list[EnvironmentSpec] = Field(default_factory=list)
    #: Groupes d'hôtes du projet, au moins un.
    groups: list[GroupSpec] = Field(default_factory=list)
    #: Configuration des rôles sélectionnés, complétée automatiquement.
    roles: list[RoleConfig] = Field(default_factory=list)
    #: Options de génération.
    options: GenerationOptions = Field(default_factory=GenerationOptions)

    @field_validator("project_name")
    @classmethod
    def _validate_project_name(cls, value: str) -> str:
        error = check_pattern(
            value,
            PROJECT_NAME_RE,
            "Nom de projet",
            "Attendu : minuscules, chiffres, '-' et '_', 2 à 63 caractères, "
            "commençant par une lettre.",
        )
        if error:
            raise ValueError(error)
        return value

    @field_validator("remote_user")
    @classmethod
    def _validate_remote_user(cls, value: str) -> str:
        error = check_pattern(
            value, USER_NAME_RE, "Nom d'utilisateur SSH", "Attendu : un nom de compte POSIX."
        )
        if error:
            raise ValueError(error)
        return value

    @field_validator("ssh_port")
    @classmethod
    def _validate_ssh_port(cls, value: int) -> int:
        if not 1 <= value <= 65535:
            raise ValueError(f"Le port SSH doit être compris entre 1 et 65535, reçu : {value}.")
        return value

    @field_validator("spec_version")
    @classmethod
    def _validate_spec_version(cls, value: int) -> int:
        if value != SPEC_VERSION:
            raise ValueError(
                f"Version de spécification non supportée : {value}. "
                f"Cette version d'ansible-forge lit le format {SPEC_VERSION}."
            )
        return value

    @model_validator(mode="after")
    def _validate_consistency(self) -> "ProjectSpec":
        if not self.environments:
            raise ValueError("Le projet doit déclarer au moins un environnement.")
        if not self.groups:
            raise ValueError("Le projet doit déclarer au moins un groupe d'hôtes.")

        env_duplicates = find_duplicates([env.name for env in self.environments])
        if env_duplicates:
            raise ValueError(f"Environnement(s) en double : {', '.join(env_duplicates)}.")

        group_names = [group.name for group in self.groups]
        group_duplicates = find_duplicates(group_names)
        if group_duplicates:
            raise ValueError(f"Groupe(s) en double : {', '.join(group_duplicates)}.")

        known_groups = set(group_names)
        for env in self.environments:
            unknown = sorted(set(env.hosts) - known_groups)
            if unknown:
                raise ValueError(
                    f"L'environnement '{env.name}' référence des groupes inconnus : "
                    f"{', '.join(unknown)}."
                )
            unknown_vars = sorted(set(env.group_vars) - known_groups - {"all"})
            if unknown_vars:
                raise ValueError(
                    f"L'environnement '{env.name}' définit des variables pour des groupes "
                    f"inconnus : {', '.join(unknown_vars)}."
                )

        self._fill_missing_role_configs()
        return self

    def _fill_missing_role_configs(self) -> None:
        """Complète ``roles`` avec les rôles référencés mais non configurés.

        Les valeurs par défaut viennent du catalogue, ce qui garantit qu'un
        ``forge.yml`` minimal produit exactement la même sortie qu'un
        ``forge.yml`` complet.
        """
        configured = {config.name for config in self.roles}
        missing = sorted(self.used_roles() - configured)
        if missing:
            self.roles.extend(RoleConfig(name=name) for name in missing)
        self.roles.sort(key=lambda config: role_names().index(config.name))

    def used_roles(self) -> set[str]:
        """Retourne l'ensemble des rôles réellement appliqués par au moins un groupe."""
        return {role for group in self.groups for role in group.roles}

    def ordered_used_roles(self) -> list[str]:
        """Retourne les rôles appliqués, triés selon l'ordre du catalogue."""
        return sort_roles(sorted(self.used_roles()))

    def role_options(self, name: str) -> dict[str, Any]:
        """Retourne les options résolues du rôle demandé."""
        for config in self.roles:
            if config.name == name:
                return config.options
        return get_role(name).default_options()
