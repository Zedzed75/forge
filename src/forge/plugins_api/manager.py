"""Plugin management facade (DESIGN.md §2.3 and §2.4).

`pm.hook.forge_answers(...)` calls *every* plugin and returns a list; forge needs
to address *one* domain at a time. This facade therefore wraps
`pm.subset_hook_caller()` behind `manager.domain("ansible").answers(spec)`.
"""

from __future__ import annotations

import importlib
import keyword
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pluggy

from forge.errors import PluginError
from forge.plugins_api import hookspecs
from forge.plugins_api.types import (
    CatalogEntry,
    Command,
    DomainInfo,
    DomainSummary,
    GenerationContext,
    Issue,
    Projection,
)

if TYPE_CHECKING:  # pragma: no cover
    from pydantic import BaseModel

    from forge.interview.prompter import Prompter
    from forge.spec.service import ServiceSpec

#: Domain plugins shipped with forge, registered statically (decision DESIGN §2.4).
#: Adding a domain must touch no other core file.
BUILTIN_PLUGINS: tuple[str, ...] = (
    "forge.plugins.ansible.plugin",
    "forge.plugins.helm.plugin",
    "forge.plugins.terraform.plugin",
    "forge.plugins.monitoring.plugin",
    "forge.plugins.pipeline.plugin",
)

#: Environment variable listing extra plugin modules, comma-separated. Used by
#: the tests (the `demo` plugin) and for local experiments.
PLUGINS_ENV_VAR = "FORGE_PLUGINS"

#: A domain name becomes both a section key in forge.yml and a **field of the
#: assembled pydantic model**. It must therefore be a lowercase Python
#: identifier that does not start with an underscore: pydantic would otherwise
#: turn the section into a private attribute, and it would vanish from the model
#: without an error.
DOMAIN_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def reserved_domain_names() -> frozenset[str]:
    """Names a domain cannot carry without overwriting part of the core.

    Computed at run time from `ForgeSpecBase`: the list cannot fall out of sync
    when a field or a method is added to it. Without this guard, a plugin named
    `service` would plainly replace the shared block in the assembled model, and
    the error would only show up much later.
    """
    from forge.spec.assembly import ForgeSpecBase

    return frozenset(
        set(ForgeSpecBase.model_fields)
        | {name for name in dir(ForgeSpecBase) if not name.startswith("__")}
    )


def check_domain_name(name: str) -> None:
    """Validate a domain name, or raise `PluginError` with the exact reason."""
    if not DOMAIN_NAME_RE.match(name) or keyword.iskeyword(name):
        raise PluginError(
            f"invalid domain name: '{name}' — expected a lowercase Python "
            "identifier starting with a letter (a-z, 0-9, _), and not a language "
            "keyword"
        )
    if name in reserved_domain_names():
        raise PluginError(
            f"reserved domain name: '{name}' collides with a field or a method of "
            "the root model; choose another domain name"
        )


class DomainHooks:
    """Single-domain view of the plugin manager.

    Each method calls the matching hook on the one plugin of the domain and
    unwraps pluggy's list of results.
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
                    f"plugin '{self.name}' does not implement the required hook "
                    f"{hook_name}()"
                )
            return None
        return results[0]

    def spec_model(self) -> type[BaseModel]:
        """Pydantic sub-model of the <domain> section."""
        return self._call("forge_spec_model", required=True)

    def template_subdir(self) -> str:
        """Path of the copier template, relative to the forge repository root."""
        return self._call("forge_template_subdir", required=True)

    def answers(self, spec: Any, context: GenerationContext | None = None) -> dict[str, Any]:
        """The `domain` dict passed to copier for this domain.

        The context — what the **other** requested domains declare — is computed
        here when the caller does not supply it. A plugin that does not need it
        does not declare the parameter: pluggy calls a hookimpl only with the
        arguments it names.
        """
        if context is None:
            context = self.manager.context(spec)
        return self._call("forge_answers", required=True, spec=spec, context=context)

    def interview(self, prompter: Prompter, service: ServiceSpec) -> dict[str, Any] | None:
        """Domain interview; None if the user declines the domain."""
        return self._call("forge_interview", required=False, prompter=prompter, service=service)

    def validators(self, spec: Any, outdir: Path) -> list[Command]:
        """External validation commands, in execution order."""
        return self._call("forge_validators", required=False, spec=spec, outdir=outdir) or []

    def deploy(self, spec: Any, outdir: Path, environment: str) -> list[Command]:
        """Commands deploying this domain into `environment`, empty if it is silent.

        The core never runs them: they are written into a pipeline.
        """
        return (
            self._call(
                "forge_deploy",
                required=False,
                spec=spec,
                outdir=outdir,
                environment=environment,
            )
            or []
        )

    def projection(self, spec: Any) -> Projection | None:
        """Projection of the domain, or None if it declares none."""
        return self._call("forge_projection", required=False, spec=spec)

    def check_spec(self, spec: Any) -> list[Issue]:
        """The domain's cross-checks on the specification, before any rendering."""
        return self._call("forge_check_spec", required=False, spec=spec) or []

    def catalog(self) -> list[CatalogEntry]:
        """Catalogue of the domain, empty if it declares none."""
        return self._call("forge_catalog", required=False) or []


class ForgeManager:
    """Plugin registry and the core's single entry point towards them."""

    def __init__(self) -> None:
        self._pm = pluggy.PluginManager(hookspecs.PROJECT_NAME)
        self._pm.add_hookspecs(hookspecs)
        self._domains: dict[str, tuple[DomainInfo, object]] = {}

    # -- registration ------------------------------------------------------

    def register(self, plugin: object, name: str | None = None) -> DomainInfo:
        """Register a plugin and return the identity of the domain it declares."""
        try:
            self._pm.register(plugin, name=name)
        except ValueError as exc:
            # pluggy refuses an already registered plugin, under the same name or
            # another one: both happen with a module listed twice.
            raise PluginError(
                f"plugin already registered: {name or plugin!r} ({exc})"
            ) from exc
        caller = self.hook_caller("forge_domain", plugin)
        results = [r for r in caller() if r is not None]
        if not results:
            self._pm.unregister(plugin)
            raise PluginError(
                f"plugin {name or plugin!r} does not implement forge_domain(): "
                "it cannot be discovered"
            )
        info = results[0]
        if not isinstance(info, DomainInfo):
            self._pm.unregister(plugin)
            raise PluginError(
                f"forge_domain() must return a DomainInfo, not {type(info).__name__}"
            )
        try:
            check_domain_name(info.name)
        except PluginError:
            self._pm.unregister(plugin)
            raise
        if info.name in self._domains:
            self._pm.unregister(plugin)
            raise PluginError(f"two plugins declare domain '{info.name}'")
        self._domains[info.name] = (info, plugin)
        return info

    def register_module(self, dotted_path: str) -> DomainInfo:
        """Import `dotted_path` and register the module as a plugin."""
        try:
            module = importlib.import_module(dotted_path)
        except Exception as exc:
            # Import failure, but also a SyntaxError or an error raised while the
            # module loads: the original type is kept, it carries the diagnosis.
            raise PluginError(
                f"unusable plugin: {dotted_path} "
                f"({type(exc).__name__}: {exc})"
            ) from exc
        return self.register(module, name=dotted_path)

    # -- lookup ------------------------------------------------------------

    def hook_caller(self, hook_name: str, plugin: object) -> Any:
        """Hook caller restricted to `plugin` alone (cf. DESIGN.md §2.3)."""
        others = [p for p in self._pm.get_plugins() if p is not plugin]
        return self._pm.subset_hook_caller(hook_name, remove_plugins=others)

    def domains(self) -> list[DomainInfo]:
        """Registered domains, sorted by name: the order is what makes it deterministic."""
        return [info for _, (info, _) in sorted(self._domains.items())]

    def domain_names(self) -> tuple[str, ...]:
        """Names of the registered domains, sorted."""
        return tuple(sorted(self._domains))

    def domain(self, name: str) -> DomainHooks:
        """Single-domain view, or `PluginError` if the domain is unknown."""
        if name not in self._domains:
            known = ", ".join(self.domain_names()) or "none"
            raise PluginError(f"unknown domain: '{name}' (known: {known})")
        info, plugin = self._domains[name]
        return DomainHooks(self, info, plugin)

    # -- overview ----------------------------------------------------------

    def context(self, spec: Any) -> GenerationContext:
        """What every domain **requested by the specification** declares.

        Only one plugin needs it — the one that federates the others — but
        nothing here is specific to it: the core gathers hooks that already
        existed, in the vocabulary of the contract, and draws no conclusion from
        them.

        Command paths are **relative to the project root**: `Path(info.outdir)`
        and not an absolute directory. The context feeds a pipeline file, where a
        developer workstation path would make no sense.

        A `PluginError` raised by a domain is not caught: a command we cannot
        build must not become a job silently missing from the pipeline.
        """
        requested = [name for name in self.domain_names() if getattr(spec, name, None) is not None]
        environments = [env.name for env in spec.service.environments]
        summaries: list[DomainSummary] = []
        for name in requested:
            hooks = self.domain(name)
            root = Path(hooks.info.outdir)
            deployments = tuple(
                (env, tuple(hooks.deploy(spec, root, env))) for env in environments
            )
            summaries.append(
                DomainSummary(
                    info=hooks.info,
                    projection=hooks.projection(spec),
                    validators=tuple(hooks.validators(spec, root)),
                    # A domain silent about deployment leaves no entry: the
                    # pipeline will write a step to fill in, not a guessed
                    # command.
                    deployments=tuple(
                        (env, commands) for env, commands in deployments if commands
                    ),
                )
            )
        return GenerationContext(domains=tuple(summaries))

    # -- multi-plugin hook -------------------------------------------------

    def consistency(self, spec: Any, outdirs: dict[str, Path]) -> list[Issue]:
        """Concatenate `forge_consistency` from every plugin (the only global hook)."""
        issues: list[Issue] = []
        for result in self._pm.hook.forge_consistency(spec=spec, outdirs=outdirs):
            if result:
                issues.extend(result)
        return issues


def default_manager() -> ForgeManager:
    """Manager populated with the shipped plugins, plus those of `FORGE_PLUGINS`."""
    manager = ForgeManager()
    for dotted in BUILTIN_PLUGINS:
        manager.register_module(dotted)
    extra = os.environ.get(PLUGINS_ENV_VAR, "")
    for dotted in (part.strip() for part in extra.split(",")):
        if dotted:
            manager.register_module(dotted)
    return manager
