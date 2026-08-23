"""Tests d'enregistrement des plugins et de la facade mono-domaine."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.errors import PluginError
from forge.plugins_api.hookspecs import hookimpl
from forge.plugins_api.manager import ForgeManager, default_manager
from forge.plugins_api.types import Command, DomainInfo, Issue, Projection
from forge.spec.types import ForgeModel


class _AutreSpec(ForgeModel):
    valeur: str = "x"


def _module_factice(name: str, outdir: str = ""):
    """Fabrique un plugin minimal sous forme d'objet porteur de hookimpls."""

    class Plugin:
        @staticmethod
        @hookimpl
        def forge_domain() -> DomainInfo:
            return DomainInfo(name=name, title=name.title(), summary="s", outdir=outdir)

        @staticmethod
        @hookimpl
        def forge_spec_model() -> type[_AutreSpec]:
            return _AutreSpec

        @staticmethod
        @hookimpl
        def forge_template_subdir() -> str:
            return f"src/forge/plugins/{name}/template"

        @staticmethod
        @hookimpl
        def forge_consistency(spec, outdirs: dict[str, Path]) -> list[Issue]:
            return [Issue(level="warning", message=f"{name} a parle", domains=(name,))]

    return Plugin()


def test_un_plugin_sans_forge_domain_est_refuse():
    class Vide:
        pass

    with pytest.raises(PluginError, match="forge_domain"):
        ForgeManager().register(Vide())


def test_deux_plugins_du_meme_domaine_sont_refuses():
    instance = ForgeManager()
    instance.register(_module_factice("alpha"), name="a")
    with pytest.raises(PluginError, match="deux plugins"):
        instance.register(_module_factice("alpha"), name="b")


def test_un_nom_de_domaine_non_identifiant_est_refuse():
    with pytest.raises(PluginError, match="nom de domaine invalide"):
        ForgeManager().register(_module_factice("mon-domaine"))


def test_les_domaines_sont_tries_par_nom():
    instance = ForgeManager()
    instance.register(_module_factice("zeta"), name="z")
    instance.register(_module_factice("alpha"), name="a")
    assert instance.domain_names() == ("alpha", "zeta")


def test_outdir_vaut_le_nom_du_domaine_par_defaut():
    assert DomainInfo(name="demo", title="D", summary="s").outdir == "demo"
    assert DomainInfo(name="demo", title="D", summary="s", outdir="sous/dir").outdir == "sous/dir"


def test_un_hook_de_domaine_n_est_pas_capte_par_un_autre_plugin(manager):
    """Le point d'attention pluggy de DESIGN.md §2.3 : chaque domaine repond pour lui."""
    manager.register(_module_factice("alpha"), name="alpha")
    assert manager.domain("demo").template_subdir() == "src/forge/plugins/demo/template"
    assert manager.domain("alpha").template_subdir() == "src/forge/plugins/alpha/template"


def test_un_domaine_inconnu_donne_un_message_actionnable(manager):
    with pytest.raises(PluginError, match="domaine inconnu"):
        manager.domain("terraform")


def test_un_hook_obligatoire_non_implemente_est_signale():
    instance = ForgeManager()

    class SansModele:
        @staticmethod
        @hookimpl
        def forge_domain() -> DomainInfo:
            return DomainInfo(name="nu", title="Nu", summary="s")

    instance.register(SansModele())
    with pytest.raises(PluginError, match="hook obligatoire"):
        instance.domain("nu").spec_model()


def test_un_hook_facultatif_absent_retourne_un_defaut_vide():
    instance = ForgeManager()
    instance.register(_module_factice("alpha"))
    assert instance.domain("alpha").catalog() == []
    assert instance.domain("alpha").validators(None, Path(".")) == []
    assert instance.domain("alpha").projection(None) is None


def test_forge_consistency_est_le_seul_hook_appele_sur_tous():
    instance = ForgeManager()
    instance.register(_module_factice("alpha"), name="alpha")
    instance.register(_module_factice("beta"), name="beta")
    issues = instance.consistency(None, {})
    assert sorted(issue.message for issue in issues) == ["alpha a parle", "beta a parle"]


def test_default_manager_lit_la_variable_d_environnement(monkeypatch):
    monkeypatch.setenv("FORGE_PLUGINS", "forge.plugins.demo.plugin")
    assert default_manager().domain_names() == ("demo",)


def test_default_manager_est_vide_sans_plugin_declare():
    assert default_manager().domain_names() == ()


def test_le_plugin_demo_declare_ses_hooks(manager, spec):
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
