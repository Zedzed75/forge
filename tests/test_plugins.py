"""Tests of plugin registration and of the single-domain facade."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from forge.errors import PluginError, SpecValidationError
from forge.plugins_api.hookspecs import hookimpl
from forge.plugins_api.manager import BUILTIN_PLUGINS, ForgeManager, default_manager
from forge.plugins_api.types import Command, DomainInfo, Issue, Projection
from forge.spec.assembly import build_spec_model
from forge.spec.types import ForgeModel
from tests.conftest import spec_files


class _OtherSpec(ForgeModel):
    value: str = "x"


def _fake_module(name: str, outdir: str = ""):
    """Build a minimal plugin as an object carrying hookimpls."""

    class Plugin:
        @staticmethod
        @hookimpl
        def forge_domain() -> DomainInfo:
            return DomainInfo(name=name, title=name.title(), summary="s", outdir=outdir)

        @staticmethod
        @hookimpl
        def forge_spec_model() -> type[_OtherSpec]:
            return _OtherSpec

        @staticmethod
        @hookimpl
        def forge_template_subdir() -> str:
            return f"src/forge/plugins/{name}/template"

        @staticmethod
        @hookimpl
        def forge_consistency(spec, outdirs: dict[str, Path]) -> list[Issue]:
            return [Issue(level="warning", message=f"{name} spoke", domains=(name,))]

    return Plugin()


def test_a_plugin_without_forge_domain_is_refused():
    class Empty:
        pass

    with pytest.raises(PluginError, match="forge_domain"):
        ForgeManager().register(Empty())


def test_two_plugins_for_the_same_domain_are_refused():
    instance = ForgeManager()
    instance.register(_fake_module("alpha"), name="a")
    with pytest.raises(PluginError, match="two plugins"):
        instance.register(_fake_module("alpha"), name="b")


def test_a_domain_name_that_is_not_an_identifier_is_refused():
    with pytest.raises(PluginError, match="invalid domain name"):
        ForgeManager().register(_fake_module("my-domain"))


@pytest.mark.parametrize("name", ["service", "forge_version", "domain_names", "section"])
def test_a_reserved_domain_name_is_refused(name):
    """Without this guard, `create_model` silently overwrites the core field."""
    with pytest.raises(PluginError, match="reserved"):
        ForgeManager().register(_fake_module(name))


def test_a_domain_name_prefixed_with_an_underscore_is_refused():
    """pydantic would make it a private attribute: the section would vanish from the model."""
    with pytest.raises(PluginError, match="invalid domain name"):
        ForgeManager().register(_fake_module("_internal"))


def test_a_domain_name_that_is_a_keyword_is_refused():
    with pytest.raises(PluginError, match="invalid domain name"):
        ForgeManager().register(_fake_module("class"))


def test_the_assembled_model_cannot_shadow_the_service_block(manager):
    """Defence in depth: even if registration is forced, assembly refuses."""
    plugin = _fake_module("service")
    manager._pm.register(plugin, name="pirate")
    manager._domains["service"] = (
        DomainInfo(name="service", title="S", summary="s"),
        plugin,
    )
    with pytest.raises(SpecValidationError, match="shadow the core"):
        build_spec_model(manager)


def test_a_module_registered_twice_gives_a_readable_error(monkeypatch):
    monkeypatch.setenv(
        "FORGE_PLUGINS", "forge.plugins.demo.plugin,forge.plugins.demo.plugin"
    )
    with pytest.raises(PluginError, match="already registered"):
        default_manager()


def test_a_missing_plugin_module_gives_a_readable_error(monkeypatch):
    monkeypatch.setenv("FORGE_PLUGINS", "forge.plugins.does.not.exist")
    with pytest.raises(PluginError, match="unusable"):
        default_manager()


def test_the_domains_are_sorted_by_name():
    instance = ForgeManager()
    instance.register(_fake_module("zeta"), name="z")
    instance.register(_fake_module("alpha"), name="a")
    assert instance.domain_names() == ("alpha", "zeta")


def test_outdir_defaults_to_the_domain_name():
    assert DomainInfo(name="demo", title="D", summary="s").outdir == "demo"
    assert DomainInfo(name="demo", title="D", summary="s", outdir="sub/dir").outdir == "sub/dir"


def test_a_domain_hook_is_not_captured_by_another_plugin(manager):
    """The pluggy caveat of DESIGN.md §2.3: each domain answers for itself."""
    manager.register(_fake_module("alpha"), name="alpha")
    assert manager.domain("demo").template_subdir() == "src/forge/plugins/demo/template"
    assert manager.domain("alpha").template_subdir() == "src/forge/plugins/alpha/template"


def test_an_unknown_domain_gives_an_actionable_message(manager):
    with pytest.raises(PluginError, match="unknown domain"):
        manager.domain("terraform")


def test_an_unimplemented_required_hook_is_reported():
    instance = ForgeManager()

    class WithoutModel:
        @staticmethod
        @hookimpl
        def forge_domain() -> DomainInfo:
            return DomainInfo(name="bare", title="Bare", summary="s")

    instance.register(WithoutModel())
    with pytest.raises(PluginError, match="required hook"):
        instance.domain("bare").spec_model()


def test_an_absent_optional_hook_returns_an_empty_default():
    instance = ForgeManager()
    instance.register(_fake_module("alpha"))
    assert instance.domain("alpha").catalog() == []
    assert instance.domain("alpha").validators(None, Path(".")) == []
    assert instance.domain("alpha").projection(None) is None


def test_forge_consistency_is_the_only_hook_called_on_everyone():
    instance = ForgeManager()
    instance.register(_fake_module("alpha"), name="alpha")
    instance.register(_fake_module("beta"), name="beta")
    issues = instance.consistency(None, {})
    assert sorted(issue.message for issue in issues) == ["alpha spoke", "beta spoke"]


def test_default_manager_reads_the_environment_variable(monkeypatch):
    monkeypatch.setenv("FORGE_PLUGINS", "forge.plugins.demo.plugin")
    assert default_manager().domain_names() == (
        "ansible",
        "demo",
        "helm",
        "monitoring",
        "pipeline",
        "terraform",
    )


def test_default_manager_registers_the_shipped_plugins():
    """The shipped domains are available without declaring anything."""
    assert default_manager().domain_names() == (
        "ansible",
        "helm",
        "monitoring",
        "pipeline",
        "terraform",
    )


def test_the_demo_plugin_declares_its_hooks(manager, spec):
    hooks = manager.domain("demo")
    answers = hooks.answers(spec)
    assert list(answers) == ["greeting", "environments", "widgets"]
    assert [w["name"] for w in answers["widgets"]] == ["cpu", "requetes"]

    projection = hooks.projection(spec)
    assert isinstance(projection, Projection)
    assert projection.environments == ("dev", "prod")

    commands = hooks.validators(spec, Path("demo"))
    assert commands and isinstance(commands[0], Command)
    assert [entry.name for entry in hooks.catalog()] == ["gauge", "counter", "log"]


# ---------------------------------------------------------------------------
# forge_check_spec: cross-check before any rendering (arbitration R2)
# ---------------------------------------------------------------------------


def test_a_cross_check_in_error_stops_the_generation(tmp_path, spec_data, manager):
    """Better to write nothing than to write a project we know to be inconsistent."""
    from forge import pipeline
    from forge.errors import SpecValidationError
    from forge.spec.assembly import validate_spec

    class Grumpy:
        @staticmethod
        @hookimpl
        def forge_domain() -> DomainInfo:
            return DomainInfo(name="grumpy", title="Grumpy", summary="s")

        @staticmethod
        @hookimpl
        def forge_spec_model() -> type[_OtherSpec]:
            return _OtherSpec

        @staticmethod
        @hookimpl
        def forge_template_subdir() -> str:
            return "src/forge/plugins/demo/template"

        @staticmethod
        @hookimpl
        def forge_check_spec(spec) -> list[Issue]:
            return [
                Issue(level="error", message="nothing works", hint="fix it", domains=("grumpy",))
            ]

    manager.register(Grumpy(), name="grumpy")
    spec_data["grumpy"] = {"value": "x"}
    spec = validate_spec(spec_data, manager)

    with pytest.raises(SpecValidationError, match="nothing works"):
        pipeline.generate(spec_data, spec, manager, tmp_path, only=["grumpy"])
    assert list(tmp_path.iterdir()) == [], "nothing must have been written"


def test_a_cross_check_in_warning_lets_it_through(tmp_path, spec_data, manager):
    from forge import pipeline
    from forge.spec.assembly import validate_spec

    class Grouchy:
        @staticmethod
        @hookimpl
        def forge_domain() -> DomainInfo:
            return DomainInfo(name="grouchy", title="Grouchy", summary="s")

        @staticmethod
        @hookimpl
        def forge_spec_model() -> type[_OtherSpec]:
            return _OtherSpec

        @staticmethod
        @hookimpl
        def forge_template_subdir() -> str:
            return "src/forge/plugins/demo/template"

        @staticmethod
        @hookimpl
        def forge_check_spec(spec) -> list[Issue]:
            return [Issue(level="warning", message="something smells", domains=("grouchy",))]

    manager.register(Grouchy(), name="grouchy")
    spec_data["grouchy"] = {"value": "x"}
    spec = validate_spec(spec_data, manager)

    result = pipeline.generate(spec_data, spec, manager, tmp_path, only=["grouchy"], dry_run=True)
    assert [issue.message for issue in result.warnings] == ["something smells"]


# ---------------------------------------------------------------------------
# Guard: a projection key must never be read in dotted notation when it carries
# the name of a dict method
# ---------------------------------------------------------------------------
#
# In Jinja, `object.values` resolves the dict **method** before the key: the
# template then writes `<built-in method values...>` into the generated file, and
# the validation tool complains very far from the cause. That happened once, on
# the monitoring domain.
#
# Renaming the keys is not the answer: the `keys` key of a Helm ConfigMap really
# is called `keys`, that is the vocabulary of the domain. The answer is the form
# of access — `c.config["keys"]`, which the Helm templates already use — and
# these two tests enforce it, one on the source, one on the output.

#: Dict method names a template must not read in dotted notation. `get` is
#: deliberately absent: `x.get(...)` is a legitimate call.
TRAP_NAMES = ("keys", "values", "items")

#: A Jinja expression of this project, `[[ ]]` or `[% %]` delimiters (decision Q1).
_JINJA_EXPRESSION = re.compile(r"\[\[.*?\]\]|\[%.*?%\]", re.DOTALL)

#: `.keys`, `.values` or `.items` not followed by a parenthesis: a key read, not
#: a method call.
#:
#: The `\b` matters twice over. It stops `.values_ref` — a key whose name merely
#: starts with `values` — from being flagged. And it has to live in a **raw**
#: string: written into an ordinary one, `"\b"` is a backspace character, which
#: no template contains, so the pattern silently matched nothing and this whole
#: guard passed on every file without reading them. That is how it was, and the
#: translation is what surfaced it.
_DOTTED_READ = re.compile(r"\.(?:" + "|".join(TRAP_NAMES) + r")\b(?!\s*\()")


def _templates() -> list[Path]:
    """Every Jinja template of the shipped domains."""
    root = Path(__file__).resolve().parents[1] / "src" / "forge" / "plugins"
    return sorted(root.rglob("*.jinja"))


@pytest.mark.parametrize(
    "template", _templates(), ids=[path.name[:40] for path in _templates()]
)
def test_no_template_reads_a_key_in_trapping_dotted_notation(template):
    """The safe form is `object["keys"]`, not `object.keys`."""
    content = template.read_bytes().decode("utf-8")
    offenders = [
        expression.group(0)
        for expression in _JINJA_EXPRESSION.finditer(content)
        if _DOTTED_READ.search(expression.group(0))
    ]
    assert offenders == [], (
        f"{template.name} reads a key in dotted notation: {offenders}. "
        'Use the subscript form — object["keys"] — otherwise Jinja resolves the '
        "dict method and writes `<built-in method ...>` into the generated file."
    )


@pytest.mark.parametrize(
    "spec_path", spec_files(), ids=[path.stem for path in spec_files()]
)
def test_no_generated_file_carries_a_python_method(spec_path, tmp_path):
    """The same check, on the output: exact, and valid for any domain.

    The source check may miss a roundabout form of access; this one cannot be
    wrong, since it reads what was actually written.
    """
    from forge import pipeline
    from forge.spec.assembly import validate_spec
    from forge.spec.io import load_spec_data

    manager = ForgeManager()
    for module in BUILTIN_PLUGINS:
        manager.register_module(module)
    data = load_spec_data(spec_path)
    if not (set(data) & set(manager.domain_names())):
        pytest.skip("no shipped domain in this specification")
    pipeline.generate(data, validate_spec(data, manager), manager, tmp_path)

    offenders = [
        path.name
        for path in tmp_path.rglob("*")
        if path.is_file()
        and any(
            pattern in path.read_bytes().decode("utf-8", errors="replace")
            for pattern in ("<built-in method", "<bound method")
        )
    ]
    assert offenders == [], f"files carrying a rendered Python method: {offenders}"
