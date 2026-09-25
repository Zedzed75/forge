"""Tests d'enregistrement des plugins et de la facade mono-domaine."""

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
    with pytest.raises(PluginError, match="two plugins"):
        instance.register(_module_factice("alpha"), name="b")


def test_un_nom_de_domaine_non_identifiant_est_refuse():
    with pytest.raises(PluginError, match="invalid domain name"):
        ForgeManager().register(_module_factice("mon-domaine"))


@pytest.mark.parametrize("nom", ["service", "forge_version", "domain_names", "section"])
def test_un_nom_de_domaine_reserve_est_refuse(nom):
    """Sans ce garde-fou, `create_model` ecrase le champ du coeur en silence."""
    with pytest.raises(PluginError, match="reserved"):
        ForgeManager().register(_module_factice(nom))


def test_un_nom_de_domaine_prefixe_par_souligne_est_refuse():
    """pydantic en ferait un attribut prive : la section disparaitrait du modele."""
    with pytest.raises(PluginError, match="invalid domain name"):
        ForgeManager().register(_module_factice("_interne"))


def test_un_nom_de_domaine_mot_cle_est_refuse():
    with pytest.raises(PluginError, match="invalid domain name"):
        ForgeManager().register(_module_factice("class"))


def test_le_modele_assemble_ne_peut_pas_masquer_le_bloc_service(manager):
    """Defense en profondeur : meme en forcant l'enregistrement, l'assemblage refuse."""
    plugin = _module_factice("service")
    manager._pm.register(plugin, name="pirate")
    manager._domains["service"] = (
        DomainInfo(name="service", title="S", summary="s"),
        plugin,
    )
    with pytest.raises(SpecValidationError, match="shadow the core"):
        build_spec_model(manager)


def test_un_module_enregistre_deux_fois_donne_une_erreur_lisible(monkeypatch):
    monkeypatch.setenv(
        "FORGE_PLUGINS", "forge.plugins.demo.plugin,forge.plugins.demo.plugin"
    )
    with pytest.raises(PluginError, match="already registered"):
        default_manager()


def test_un_module_de_plugin_introuvable_donne_une_erreur_lisible(monkeypatch):
    monkeypatch.setenv("FORGE_PLUGINS", "forge.plugins.nexiste.pas")
    with pytest.raises(PluginError, match="unusable"):
        default_manager()


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
    with pytest.raises(PluginError, match="unknown domain"):
        manager.domain("terraform")


def test_un_hook_obligatoire_non_implemente_est_signale():
    instance = ForgeManager()

    class SansModele:
        @staticmethod
        @hookimpl
        def forge_domain() -> DomainInfo:
            return DomainInfo(name="nu", title="Nu", summary="s")

    instance.register(SansModele())
    with pytest.raises(PluginError, match="required hook"):
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
    assert default_manager().domain_names() == (
        "ansible",
        "demo",
        "helm",
        "monitoring",
        "pipeline",
        "terraform",
    )


def test_default_manager_enregistre_les_plugins_livres():
    """Les domaines livres sont disponibles sans rien declarer."""
    assert default_manager().domain_names() == (
        "ansible",
        "helm",
        "monitoring",
        "pipeline",
        "terraform",
    )


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


# ---------------------------------------------------------------------------
# forge_check_spec : controle croise avant tout rendu (arbitrage R2)
# ---------------------------------------------------------------------------


def test_un_controle_croise_en_erreur_arrete_la_generation(tmp_path, spec_data, manager):
    """Mieux vaut ne rien ecrire que d'ecrire un projet qu'on sait incoherent."""
    from forge import pipeline
    from forge.errors import SpecValidationError
    from forge.spec.assembly import validate_spec

    class Grognon:
        @staticmethod
        @hookimpl
        def forge_domain() -> DomainInfo:
            return DomainInfo(name="grognon", title="Grognon", summary="s")

        @staticmethod
        @hookimpl
        def forge_spec_model() -> type[_AutreSpec]:
            return _AutreSpec

        @staticmethod
        @hookimpl
        def forge_template_subdir() -> str:
            return "src/forge/plugins/demo/template"

        @staticmethod
        @hookimpl
        def forge_check_spec(spec) -> list[Issue]:
            return [
                Issue(level="error", message="rien ne va", hint="corrigez", domains=("grognon",))
            ]

    manager.register(Grognon(), name="grognon")
    spec_data["grognon"] = {"valeur": "x"}
    spec = validate_spec(spec_data, manager)

    with pytest.raises(SpecValidationError, match="rien ne va"):
        pipeline.generate(spec_data, spec, manager, tmp_path, only=["grognon"])
    assert list(tmp_path.iterdir()) == [], "rien ne doit avoir ete ecrit"


def test_un_controle_croise_en_avertissement_laisse_passer(tmp_path, spec_data, manager):
    from forge import pipeline
    from forge.spec.assembly import validate_spec

    class Ronchon:
        @staticmethod
        @hookimpl
        def forge_domain() -> DomainInfo:
            return DomainInfo(name="ronchon", title="Ronchon", summary="s")

        @staticmethod
        @hookimpl
        def forge_spec_model() -> type[_AutreSpec]:
            return _AutreSpec

        @staticmethod
        @hookimpl
        def forge_template_subdir() -> str:
            return "src/forge/plugins/demo/template"

        @staticmethod
        @hookimpl
        def forge_check_spec(spec) -> list[Issue]:
            return [Issue(level="warning", message="ca sent le roussi", domains=("ronchon",))]

    manager.register(Ronchon(), name="ronchon")
    spec_data["ronchon"] = {"valeur": "x"}
    spec = validate_spec(spec_data, manager)

    result = pipeline.generate(spec_data, spec, manager, tmp_path, only=["ronchon"], dry_run=True)
    assert [issue.message for issue in result.warnings] == ["ca sent le roussi"]


# ---------------------------------------------------------------------------
# Garde-fou : une cle de projection ne doit jamais etre lue en notation pointee
# quand elle porte le nom d'une methode de dict
# ---------------------------------------------------------------------------
#
# En Jinja, `objet.values` resout la **methode** du dict avant la cle : le
# gabarit ecrit alors `<built-in method values...>` dans le fichier genere, et
# l'outil de validation s'en plaint tres loin de la cause. C'est arrive une fois
# sur le domaine monitoring.
#
# Renommer les cles n'est pas la reponse : la cle `keys` d'un ConfigMap Helm
# s'appelle bien `keys`, c'est le vocabulaire du domaine. La reponse est la
# forme d'acces — `c.config["keys"]`, que les gabarits Helm emploient deja — et
# ces deux tests l'imposent, l'un sur la source, l'autre sur la sortie.

#: Noms de methode de dict qu'un gabarit ne doit pas lire en notation pointee.
#: `get` est volontairement absent : `x.get(...)` est un appel legitime.
NOMS_PIEGES = ("keys", "values", "items")

#: Une expression Jinja du projet, delimiteurs `[[ ]]` ou `[% %]` (decision Q1).
_EXPRESSION_JINJA = re.compile(r"\[\[.*?\]\]|\[%.*?%\]", re.DOTALL)

#: `.keys`, `.values` ou `.items` non suivi d'une parenthese : une lecture de
#: cle, pas un appel de methode.
_LECTURE_POINTEE = re.compile(r"\.(?:" + "|".join(NOMS_PIEGES) + r")(?!\s*\()")


def _gabarits() -> list[Path]:
    """Tous les gabarits Jinja des domaines livres."""
    racine = Path(__file__).resolve().parents[1] / "src" / "forge" / "plugins"
    return sorted(racine.rglob("*.jinja"))


@pytest.mark.parametrize(
    "gabarit", _gabarits(), ids=[chemin.name[:40] for chemin in _gabarits()]
)
def test_aucun_gabarit_ne_lit_une_cle_en_notation_pointee_piegeuse(gabarit):
    """La forme sure est `objet["keys"]`, pas `objet.keys`."""
    contenu = gabarit.read_bytes().decode("utf-8")
    fautives = [
        expression.group(0)
        for expression in _EXPRESSION_JINJA.finditer(contenu)
        if _LECTURE_POINTEE.search(expression.group(0))
    ]
    assert fautives == [], (
        f"{gabarit.name} lit une cle en notation pointee : {fautives}. "
        'Employez la forme indicee — objet["keys"] — sans quoi Jinja resout la '
        "methode du dict et ecrit `<built-in method ...>` dans le fichier genere."
    )


@pytest.mark.parametrize(
    "spec_path", spec_files(), ids=[chemin.stem for chemin in spec_files()]
)
def test_aucun_fichier_genere_ne_porte_de_methode_python(spec_path, tmp_path):
    """Le meme controle, sur la sortie : exact, et valable pour tout domaine.

    Le controle sur la source peut manquer une forme d'acces detournee ; celui-ci
    ne peut pas se tromper, puisqu'il lit ce qui a reellement ete ecrit.
    """
    from forge import pipeline
    from forge.spec.assembly import validate_spec
    from forge.spec.io import load_spec_data

    manager = ForgeManager()
    for module in BUILTIN_PLUGINS:
        manager.register_module(module)
    data = load_spec_data(spec_path)
    if not (set(data) & set(manager.domain_names())):
        pytest.skip("aucun domaine livre dans cette specification")
    pipeline.generate(data, validate_spec(data, manager), manager, tmp_path)

    fautifs = [
        chemin.name
        for chemin in tmp_path.rglob("*")
        if chemin.is_file()
        and any(
            motif in chemin.read_bytes().decode("utf-8", errors="replace")
            for motif in ("<built-in method", "<bound method")
        )
    ]
    assert fautifs == [], f"fichiers portant une methode Python rendue : {fautifs}"
