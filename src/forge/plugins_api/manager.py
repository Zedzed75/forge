"""Facade de gestion des plugins (DESIGN.md §2.3 et §2.4).

`pm.hook.forge_answers(...)` appelle *tous* les plugins et retourne une liste ;
forge a besoin d'adresser *un* domaine a la fois. Cette facade encapsule donc
`pm.subset_hook_caller()` derriere `manager.domain("ansible").answers(spec)`.
"""

from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pluggy

from forge.errors import PluginError
from forge.plugins_api import hookspecs
from forge.plugins_api.types import CatalogEntry, Command, DomainInfo, Issue, Projection

if TYPE_CHECKING:  # pragma: no cover
    from pydantic import BaseModel

    from forge.interview.prompter import Prompter
    from forge.spec.service import ServiceSpec

#: Plugins de domaine livres avec forge, enregistres en dur (decision DESIGN §2.4).
#: Ajouter un domaine ne doit toucher aucun autre fichier du coeur.
BUILTIN_PLUGINS: tuple[str, ...] = ()

#: Variable d'environnement listant des modules de plugin supplementaires,
#: separes par des virgules. Sert aux tests (plugin `demo`) et aux essais locaux.
PLUGINS_ENV_VAR = "FORGE_PLUGINS"


class DomainHooks:
    """Vue mono-domaine du gestionnaire de plugins.

    Chaque methode appelle le hook correspondant sur le seul plugin du domaine
    et deplie la liste de resultats de pluggy.
    """

    def __init__(self, manager: ForgeManager, info: DomainInfo, plugin: object) -> None:
        self.manager = manager
        self.info = info
        self.plugin = plugin

    @property
    def name(self) -> str:
        return self.info.name

    def _call(self, hook_name: str, required: bool, **kwargs: Any) -> Any:
        caller = self.manager.hook_caller(hook_name, self.plugin)
        results = caller(**kwargs)
        results = [r for r in results if r is not None]
        if not results:
            if required:
                raise PluginError(
                    f"le plugin '{self.name}' n'implemente pas le hook obligatoire "
                    f"{hook_name}()"
                )
            return None
        return results[0]

    def spec_model(self) -> type[BaseModel]:
        """Sous-modele pydantic de la section <domaine>."""
        return self._call("forge_spec_model", required=True)

    def template_subdir(self) -> str:
        """Chemin du gabarit copier, relatif a la racine du depot forge."""
        return self._call("forge_template_subdir", required=True)

    def answers(self, spec: Any) -> dict[str, Any]:
        """Dict `domain` passe a copier pour ce domaine."""
        return self._call("forge_answers", required=True, spec=spec)

    def interview(self, prompter: Prompter, service: ServiceSpec) -> dict[str, Any] | None:
        """Entretien du domaine ; None si l'utilisateur decline le domaine."""
        return self._call("forge_interview", required=False, prompter=prompter, service=service)

    def validators(self, spec: Any, outdir: Path) -> list[Command]:
        """Commandes externes de validation, dans l'ordre d'execution."""
        return self._call("forge_validators", required=False, spec=spec, outdir=outdir) or []

    def projection(self, spec: Any) -> Projection | None:
        """Projection du domaine, ou None s'il n'en declare pas."""
        return self._call("forge_projection", required=False, spec=spec)

    def catalog(self) -> list[CatalogEntry]:
        """Catalogue du domaine, vide s'il n'en declare pas."""
        return self._call("forge_catalog", required=False) or []


class ForgeManager:
    """Registre des plugins et point d'entree unique du coeur vers eux."""

    def __init__(self) -> None:
        self._pm = pluggy.PluginManager(hookspecs.PROJECT_NAME)
        self._pm.add_hookspecs(hookspecs)
        self._domains: dict[str, tuple[DomainInfo, object]] = {}

    # -- enregistrement ----------------------------------------------------

    def register(self, plugin: object, name: str | None = None) -> DomainInfo:
        """Enregistre un plugin et retourne l'identite du domaine qu'il declare."""
        self._pm.register(plugin, name=name)
        caller = self.hook_caller("forge_domain", plugin)
        results = [r for r in caller() if r is not None]
        if not results:
            self._pm.unregister(plugin)
            raise PluginError(
                f"le plugin {name or plugin!r} n'implemente pas forge_domain() : "
                "il ne peut pas etre decouvert"
            )
        info = results[0]
        if not isinstance(info, DomainInfo):
            self._pm.unregister(plugin)
            raise PluginError(
                f"forge_domain() doit retourner un DomainInfo, pas {type(info).__name__}"
            )
        if not info.name.isidentifier() or info.name != info.name.lower():
            # Le nom devient un champ du modele pydantic assemble : il doit etre
            # un identifiant Python minuscule (pas de tiret, pas d'espace).
            self._pm.unregister(plugin)
            raise PluginError(
                f"nom de domaine invalide : '{info.name}' — attendu un identifiant "
                "Python en minuscules (a-z, 0-9, _)"
            )
        if info.name in self._domains:
            self._pm.unregister(plugin)
            raise PluginError(f"deux plugins declarent le domaine '{info.name}'")
        self._domains[info.name] = (info, plugin)
        return info

    def register_module(self, dotted_path: str) -> DomainInfo:
        """Importe `dotted_path` et enregistre le module comme plugin."""
        try:
            module = importlib.import_module(dotted_path)
        except ImportError as exc:  # pragma: no cover - depend de l'environnement
            raise PluginError(f"plugin introuvable : {dotted_path} ({exc})") from exc
        return self.register(module, name=dotted_path)

    # -- consultation ------------------------------------------------------

    def hook_caller(self, hook_name: str, plugin: object) -> Any:
        """Hook caller restreint au seul `plugin` (cf. DESIGN.md §2.3)."""
        others = [p for p in self._pm.get_plugins() if p is not plugin]
        return self._pm.subset_hook_caller(hook_name, remove_plugins=others)

    def domains(self) -> list[DomainInfo]:
        """Domaines enregistres, tries par nom : l'ordre fait le determinisme."""
        return [info for _, (info, _) in sorted(self._domains.items())]

    def domain_names(self) -> tuple[str, ...]:
        """Noms des domaines enregistres, tries."""
        return tuple(sorted(self._domains))

    def domain(self, name: str) -> DomainHooks:
        """Vue mono-domaine, ou `PluginError` si le domaine est inconnu."""
        if name not in self._domains:
            known = ", ".join(self.domain_names()) or "aucun"
            raise PluginError(f"domaine inconnu : '{name}' (connus : {known})")
        info, plugin = self._domains[name]
        return DomainHooks(self, info, plugin)

    # -- hook multi-plugins ------------------------------------------------

    def consistency(self, spec: Any, outdirs: dict[str, Path]) -> list[Issue]:
        """Concatene `forge_consistency` de tous les plugins (seul hook global)."""
        issues: list[Issue] = []
        for result in self._pm.hook.forge_consistency(spec=spec, outdirs=outdirs):
            if result:
                issues.extend(result)
        return issues


def default_manager() -> ForgeManager:
    """Gestionnaire peuple des plugins livres, plus ceux de `FORGE_PLUGINS`."""
    manager = ForgeManager()
    for dotted in BUILTIN_PLUGINS:
        manager.register_module(dotted)
    extra = os.environ.get(PLUGINS_ENV_VAR, "")
    for dotted in (part.strip() for part in extra.split(",")):
        if dotted:
            manager.register_module(dotted)
    return manager
