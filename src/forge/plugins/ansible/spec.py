"""Section `ansible:` de forge.yml.

Portage de `ansible_forge.models.spec` (MIGRATION.md §3). L'identite du projet
— nom, description, auteur, liste des environnements — est montee dans le bloc
partage `service:` du coeur ; ce qui reste ici decrit **comment Ansible parle
aux machines** : famille d'OS, compte distant, groupes, hotes, roles.

Deux normalisations du legacy sont conservees telles quelles, parce qu'elles
rendent une specification partielle equivalente a une specification complete —
et donc le rendu reproductible :

* les options de role absentes prennent le defaut du catalogue, et le dict est
  reordonne selon l'ordre de declaration des options ;
* un role applique par un groupe mais absent de `roles:` est ajoute avec ses
  defauts, puis toute la liste est triee dans l'ordre fige du catalogue.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import Field, field_validator, model_validator

from forge.plugins.ansible.catalog.registry import (
    role_names,
    sort_roles,
    validate_options,
)
from forge.plugins.ansible.names import (
    GROUP_NAME_RE,
    HOST_NAME_RE,
    MAX_PORT,
    MIN_PORT,
    RESERVED_GROUP_NAMES,
    check_var_names,
)
from forge.spec.names import find_duplicates
from forge.spec.types import ForgeModel


class OSFamily(str, Enum):
    """Famille de systeme d'exploitation ciblee par le projet.

    Elle conditionne les paquets, les services et les chemins de configuration
    employes par les roles generes.
    """

    DEBIAN = "debian"
    REDHAT = "redhat"


class HostSpec(ForgeModel):
    """Une machine d'inventaire."""

    #: Nom d'inventaire de la machine ; sert de nom de fichier host_vars.
    name: str

    #: Adresse ou nom resolvable employe pour la connexion SSH.
    ansible_host: str

    #: Port SSH propre a cette machine ; absent = valeur globale du projet.
    ansible_port: int | None = None

    #: Compte SSH propre a cette machine ; absent = valeur globale du projet.
    ansible_user: str | None = None

    #: Variables libres ecrites dans host_vars/<machine>.yml.
    vars: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def _valid_name(cls, value: str) -> str:
        if not HOST_NAME_RE.match(value):
            raise ValueError(
                f"Nom d'hote invalide : '{value}'. Attendu : minuscules, chiffres, "
                "points, tirets et soulignes."
            )
        return value

    @field_validator("ansible_port")
    @classmethod
    def _valid_port(cls, value: int | None) -> int | None:
        if value is not None and not MIN_PORT <= value <= MAX_PORT:
            raise ValueError(f"Port SSH hors bornes : {value} (attendu {MIN_PORT}-{MAX_PORT}).")
        return value

    @field_validator("vars")
    @classmethod
    def _valid_vars(cls, value: dict[str, Any]) -> dict[str, Any]:
        return check_var_names(value, "host_vars")


class GroupSpec(ForgeModel):
    """Un groupe d'hotes et les roles qui lui sont appliques."""

    #: Nom du groupe Ansible.
    name: str

    #: Description reprise dans l'inventaire et les playbooks generes.
    description: str = ""

    #: Roles appliques au groupe ; reordonnes dans l'ordre du catalogue.
    roles: list[str] = Field(default_factory=lambda: ["common"])

    #: Variables libres ecrites dans group_vars/<groupe>.yml.
    vars: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def _valid_name(cls, value: str) -> str:
        if not GROUP_NAME_RE.match(value):
            raise ValueError(
                f"Nom de groupe invalide : '{value}'. Attendu : minuscules, chiffres "
                "et soulignes (les tirets sont interdits par Ansible)."
            )
        if value in RESERVED_GROUP_NAMES:
            reserves = ", ".join(sorted(RESERVED_GROUP_NAMES))
            raise ValueError(
                f"Le nom de groupe '{value}' est reserve par Ansible ({reserves})."
            )
        return value

    @field_validator("roles")
    @classmethod
    def _valid_roles(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("Un groupe doit appliquer au moins un role.")
        doublons = find_duplicates(value)
        if doublons:
            raise ValueError(
                f"Role(s) en double dans le groupe : {', '.join(sorted(doublons))}."
            )
        connus = role_names()
        inconnus = [nom for nom in value if nom not in connus]
        if inconnus:
            raise ValueError(
                f"Role inconnu : '{inconnus[0]}'. Roles disponibles : {', '.join(connus)}."
            )
        return sort_roles(value)

    @field_validator("vars")
    @classmethod
    def _valid_vars(cls, value: dict[str, Any]) -> dict[str, Any]:
        return check_var_names(value, "group_vars")


class RoleConfig(ForgeModel):
    """Les options choisies pour un role du catalogue."""

    #: Nom du role, tel qu'il figure au catalogue.
    name: str

    #: Options du role ; completees par les defauts du catalogue a la validation.
    options: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _fill_defaults(cls, data: Any) -> Any:
        """Complete et reordonne les options a partir du catalogue.

        C'est ce qui rend un forge.yml partiel equivalent a un forge.yml complet :
        les deux produisent le meme objet, donc la meme sortie.
        """
        if not isinstance(data, dict):
            return data
        nom = data.get("name")
        if not isinstance(nom, str) or nom not in role_names():
            return data  # nom invalide : le validateur de champ dira pourquoi
        data = dict(data)
        data["options"] = validate_options(nom, data.get("options") or {})
        return data

    @field_validator("name")
    @classmethod
    def _valid_name(cls, value: str) -> str:
        if value not in role_names():
            raise ValueError(
                f"Role inconnu : '{value}'. Roles disponibles : {', '.join(role_names())}."
            )
        return value


class GenerationOptions(ForgeModel):
    """Ce que le projet genere embarque, en plus des roles et de l'inventaire."""

    #: Ecrit un fichier d'exemple de coffre par environnement.
    use_vault: bool = True

    #: Ecrit .ansible-lint, .yamllint et .gitignore a la racine du projet.
    write_lint_config: bool = True

    #: Ecrit un workflow GitHub Actions lancant ansible-lint.
    write_ci: bool = False


class AnsibleSpec(ForgeModel):
    """Section `ansible:` complete."""

    #: Famille d'OS ciblee : conditionne paquets, services et chemins.
    os_family: OSFamily = OSFamily.DEBIAN

    #: Compte SSH employe par defaut pour joindre les machines.
    remote_user: str = "ansible"

    #: Passe par `become` (sudo) pour les taches privilegiees.
    become: bool = True

    #: Port SSH employe par defaut.
    ssh_port: int = 22

    #: Interpreteur Python des machines cibles (`auto_silent` ou chemin absolu).
    python_interpreter: str = "auto_silent"

    #: Ce que le projet genere embarque en plus des roles.
    options: GenerationOptions = Field(default_factory=GenerationOptions)

    #: Groupes d'hotes ; l'ordre est celui de l'inventaire et de site.yml.
    groups: list[GroupSpec] = Field(min_length=1)

    #: Machines par environnement puis par groupe : hosts[env][groupe].
    hosts: dict[str, dict[str, list[HostSpec]]] = Field(default_factory=dict)

    #: Variables d'inventaire par environnement puis par portee (`all` ou groupe).
    group_vars: dict[str, dict[str, dict[str, Any]]] = Field(default_factory=dict)

    #: Options des roles ; completee a la validation par les roles appliques.
    roles: list[RoleConfig] = Field(default_factory=list)

    # -- validation ---------------------------------------------------------

    @field_validator("ssh_port")
    @classmethod
    def _valid_port(cls, value: int) -> int:
        if not MIN_PORT <= value <= MAX_PORT:
            raise ValueError(f"Port SSH hors bornes : {value} (attendu {MIN_PORT}-{MAX_PORT}).")
        return value

    @field_validator("groups")
    @classmethod
    def _unique_groups(cls, value: list[GroupSpec]) -> list[GroupSpec]:
        doublons = find_duplicates(groupe.name for groupe in value)
        if doublons:
            raise ValueError(f"Groupe(s) en double : {', '.join(sorted(doublons))}.")
        return value

    @model_validator(mode="after")
    def _check_references(self) -> AnsibleSpec:
        """Verifie que hosts et group_vars ne citent que des groupes declares."""
        connus = {groupe.name for groupe in self.groups}
        for env, par_groupe in self.hosts.items():
            inconnus = sorted(set(par_groupe) - connus)
            if inconnus:
                raise ValueError(
                    f"L'environnement '{env}' reference des groupes inconnus : "
                    f"{', '.join(inconnus)}."
                )
            noms = [hote.name for groupe in par_groupe.values() for hote in groupe]
            doublons = find_duplicates(noms)
            if doublons:
                raise ValueError(
                    f"Hote(s) declare(s) plusieurs fois dans l'environnement '{env}' : "
                    f"{', '.join(sorted(doublons))}."
                )
        for env, par_portee in self.group_vars.items():
            inconnus = sorted(set(par_portee) - connus - {"all"})
            if inconnus:
                raise ValueError(
                    f"L'environnement '{env}' definit des variables pour des groupes "
                    f"inconnus : {', '.join(inconnus)}."
                )
            for portee, variables in par_portee.items():
                check_var_names(variables, f"inventories/{env}/group_vars/{portee}")
        return self

    @model_validator(mode="after")
    def _fill_missing_roles(self) -> AnsibleSpec:
        """Ajoute les roles appliques mais non configures, puis trie le catalogue."""
        configures = {config.name for config in self.roles}
        for nom in sorted(self.used_roles() - configures):
            self.roles.append(RoleConfig(name=nom))
        ordre = role_names()
        self.roles.sort(key=lambda config: ordre.index(config.name))
        return self

    # -- consultation -------------------------------------------------------

    def used_roles(self) -> set[str]:
        """Roles reellement appliques par au moins un groupe."""
        return {nom for groupe in self.groups for nom in groupe.roles}

    def ordered_used_roles(self) -> list[str]:
        """Roles appliques, dans l'ordre fige du catalogue."""
        return sort_roles(self.used_roles())

    def group(self, name: str) -> GroupSpec:
        """Retourne le groupe `name`, ou leve `KeyError`."""
        for groupe in self.groups:
            if groupe.name == name:
                return groupe
        raise KeyError(name)

    def role_options(self, name: str) -> dict[str, Any]:
        """Options retenues pour le role `name`, defauts du catalogue compris."""
        for config in self.roles:
            if config.name == name:
                return config.options
        return validate_options(name, {})
