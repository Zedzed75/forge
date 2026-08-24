"""Couverture des chemins que la suite initiale ne touchait pas.

Chaque test de ce module correspond a un defaut demontre par l'audit du coeur :
un comportement que l'on pouvait supprimer entierement du code sans qu'un seul
test passe au rouge. Ils tiennent a part du reste des tests de CLI pour rester
lisibles, et parce qu'ils ont besoin de **plusieurs** domaines enregistres, ce
que le seul plugin `demo` ne permet pas.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from forge import pipeline
from forge.cli import app
from forge.errors import RenderError
from forge.plugins_api.manager import ForgeManager
from forge.spec.assembly import validate_spec
from forge.spec.io import save_spec
from tests.conftest import DEMO_PLUGIN, REPO_ROOT, SPECS_DIR, build_project, load_case

runner = CliRunner()

#: Modules des domaines factices, importables par `FORGE_PLUGINS`.
AUTRE = "tests.domaines_factices.autre"
NORMAL = "tests.domaines_factices.normal"
DIVERGENT = "tests.domaines_factices.divergent"
DESORDRE = "tests.domaines_factices.desordre"
FRAGILE = "tests.domaines_factices.outil_absent"

#: Domaine factice dont le paquet ne fournit aucun module de filtres.
ISOLE = "tests.domaine_isole"

#: Cles de forge.yml qui ne sont pas des sections de domaine.
CLES_DU_COEUR = ("forge_version", "service")


def _invoke(args: list[str], monkeypatch: pytest.MonkeyPatch, plugins: str = DEMO_PLUGIN):
    monkeypatch.setenv("FORGE_PLUGINS", plugins)
    return runner.invoke(app, args)


def _manager(*modules: str) -> ForgeManager:
    """Gestionnaire peuple des modules de plugin demandes."""
    instance = ForgeManager()
    for module in modules or (DEMO_PLUGIN,):
        instance.register_module(module)
    return instance


def _ecrire_spec(path: Path, data: dict) -> Path:
    """Ecrit une specification de test, sans passer par la CLI."""
    sections = [key for key in data if key not in CLES_DU_COEUR]
    save_spec(data, path, sections=sections)
    return path


def _spec_deux_domaines() -> dict:
    """Specification demandant le domaine `demo` ET le domaine `autre`."""
    section = {"greeting": "bonjour", "widgets": [{"name": "cpu", "kind": "gauge"}]}
    return {
        "forge_version": 1,
        "service": {
            "name": "boutique",
            "description": "Boutique en ligne",
            "owner": "Equipe Plateforme",
            "environments": [{"name": "prod", "production": True}],
        },
        "demo": dict(section),
        "autre": dict(section),
    }


def _spec_factice(*domaines: str) -> dict:
    """Specification n'activant que des domaines factices sans contenu."""
    data: dict = {
        "forge_version": 1,
        "service": {
            "name": "boutique",
            "description": "Boutique en ligne",
            "owner": "Equipe Plateforme",
            "environments": [{"name": "dev"}, {"name": "prod", "production": True}],
        },
    }
    for nom in domaines:
        data[nom] = {"enabled": True}
    return data


# ---------------------------------------------------------------------------
# Filtrage --only : il exige deux domaines enregistres
# ---------------------------------------------------------------------------


def test_only_ne_genere_que_le_domaine_demande(tmp_path):
    """Sans ce filtre, `--only helm` regenererait aussi `ansible/`, ecrasant des
    fichiers que l'utilisateur avait explicitement exclus."""
    manager = _manager(DEMO_PLUGIN, AUTRE)
    data = _spec_deux_domaines()
    pipeline.generate(data, validate_spec(data, manager), manager, tmp_path, only=["demo"])

    assert (tmp_path / "demo").is_dir()
    assert not (tmp_path / "autre").exists()


def test_only_ne_retire_pas_les_autres_domaines_de_l_index(tmp_path):
    """L'index de niveau depot decrit la SPECIFICATION, pas le dernier filtre."""
    manager = _manager(DEMO_PLUGIN, AUTRE)
    data = _spec_deux_domaines()
    pipeline.generate(data, validate_spec(data, manager), manager, tmp_path, only=["demo"])

    readme = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "`demo/`" in readme
    assert "`autre/`" in readme
    assert "#   - autre" in (tmp_path / "forge.yml").read_text(encoding="utf-8")


def test_les_deux_domaines_sont_generes_sans_filtre(tmp_path):
    manager = _manager(DEMO_PLUGIN, AUTRE)
    data = _spec_deux_domaines()
    result = pipeline.generate(data, validate_spec(data, manager), manager, tmp_path)

    assert result.domains == ["autre", "demo"]
    assert (tmp_path / "autre" / "environments" / "prod" / "cpu.yml").is_file()
    assert (tmp_path / "demo" / "environments" / "prod" / "cpu.yml").is_file()


# ---------------------------------------------------------------------------
# validate : code de sortie et outils manquants
# ---------------------------------------------------------------------------


def test_validate_sort_en_1_quand_un_controle_inter_domaines_echoue(tmp_path, monkeypatch):
    """Sans ce test, la disparition du code de sortie 1 ne casserait rien."""
    spec_path = _ecrire_spec(tmp_path / "forge.yml", _spec_factice("normal", "divergent"))
    result = _invoke(
        ["validate", "-s", str(spec_path), "-o", str(tmp_path)],
        monkeypatch,
        plugins=f"{NORMAL},{DIVERGENT}",
    )
    assert result.exit_code == 1, result.stdout
    assert "ERREUR" in result.stdout
    assert "nom de service" in result.stdout


def test_validate_sort_en_0_sur_un_simple_avertissement(tmp_path, monkeypatch):
    spec_path = _ecrire_spec(tmp_path / "forge.yml", _spec_factice("normal", "desordre"))
    result = _invoke(
        ["validate", "-s", str(spec_path), "-o", str(tmp_path)],
        monkeypatch,
        plugins=f"{NORMAL},{DESORDRE}",
    )
    assert result.exit_code == 0, result.stdout
    assert "AVERTIR" in result.stdout


def test_validate_echoue_quand_un_outil_est_absent(tmp_path, monkeypatch):
    spec_path = _ecrire_spec(tmp_path / "forge.yml", _spec_factice("fragile"))
    result = _invoke(
        ["validate", "-s", str(spec_path), "-o", str(tmp_path)],
        monkeypatch,
        plugins=FRAGILE,
    )
    assert result.exit_code == 1
    assert "ABSENT" in result.stdout
    assert "c'est le but du test" in result.stdout


def test_skip_missing_passe_mais_avertit_que_rien_n_a_ete_verifie(tmp_path, monkeypatch):
    spec_path = _ecrire_spec(tmp_path / "forge.yml", _spec_factice("fragile"))
    result = _invoke(
        ["validate", "-s", str(spec_path), "-o", str(tmp_path), "--skip-missing"],
        monkeypatch,
        plugins=FRAGILE,
    )
    assert result.exit_code == 0, result.stdout
    assert "SAUTE" in result.stdout
    assert "ATTENTION" in result.stdout


# ---------------------------------------------------------------------------
# update : le test d'integration ne suffit pas, il ne tourne pas sur depot sale
# ---------------------------------------------------------------------------


def test_update_appelle_copier_pour_chaque_domaine_genere(tmp_path, monkeypatch):
    """Toujours execute : il tue la mutation « un update qui n'update rien »."""
    build_project(tmp_path)
    appels: list[dict] = []

    def espion(**kwargs):
        appels.append(kwargs)
        return kwargs["dst"]

    monkeypatch.setattr(pipeline.copier_runner, "run_update", espion)
    updated = pipeline.update(_manager(), tmp_path, ref="v1.2.3", conflict="rej")

    assert updated == ["demo"]
    assert len(appels) == 1
    assert appels[0]["dst"] == tmp_path / "demo"
    assert appels[0]["ref"] == "v1.2.3"
    assert appels[0]["conflict"] == "rej"


def test_update_refuse_un_domaine_inconnu(tmp_path, monkeypatch):
    """Une faute de frappe dans un script de CI ne doit pas sortir en 0."""
    result = _invoke(["update", "-o", str(tmp_path), "--only", "dmeo"], monkeypatch)
    assert result.exit_code == 1


def test_update_refuse_un_domaine_nomme_mais_jamais_genere(tmp_path):
    with pytest.raises(RenderError, match="copier-answers"):
        pipeline.update(_manager(), tmp_path, only=["demo"])


# ---------------------------------------------------------------------------
# generate : conflits, forge.yml de l'utilisateur, erreurs systeme
# ---------------------------------------------------------------------------


def test_generate_refuse_d_ecraser_un_fichier_modifie_sans_force(tmp_path, monkeypatch):
    """Sans ce controle, copier ouvre un prompt et casse sous Git Bash."""
    build_project(tmp_path)
    cible = tmp_path / "demo" / "README.md"
    cible.write_text("edite a la main\n", encoding="utf-8")

    result = _invoke(
        ["generate", "-s", str(SPECS_DIR / "demo-complet.yml"), "-o", str(tmp_path)],
        monkeypatch,
    )
    assert result.exit_code == 1
    assert cible.read_text(encoding="utf-8") == "edite a la main\n"

    force = _invoke(
        [
            "generate",
            "-s",
            str(SPECS_DIR / "demo-complet.yml"),
            "-o",
            str(tmp_path),
            "--force",
        ],
        monkeypatch,
    )
    assert force.exit_code == 0, force.stdout
    assert "Domaine demo" in cible.read_text(encoding="utf-8")


def test_generate_preserve_les_commentaires_du_forge_yml_de_la_cible(tmp_path, monkeypatch):
    """La spec de la cible est la source de verite : la reserialiser la mutilerait."""
    build_project(tmp_path)
    spec_path = tmp_path / "forge.yml"
    spec_path.write_text(
        spec_path.read_text(encoding="utf-8") + "\n# NOTE MAISON : ne pas toucher\n",
        encoding="utf-8",
    )

    result = _invoke(["generate", "-o", str(tmp_path), "--force"], monkeypatch)
    assert result.exit_code == 0, result.stdout
    assert "NOTE MAISON" in spec_path.read_text(encoding="utf-8")


def test_generate_vers_un_fichier_donne_une_erreur_lisible(tmp_path, monkeypatch):
    fichier = tmp_path / "rapport.txt"
    fichier.write_text("x", encoding="utf-8")
    result = _invoke(
        ["generate", "-s", str(SPECS_DIR / "demo-complet.yml"), "-o", str(fichier)],
        monkeypatch,
    )
    assert result.exit_code == 1
    assert "Traceback" not in result.stdout


# ---------------------------------------------------------------------------
# diff : les fichiers de niveau depot ne passent pas par copier
# ---------------------------------------------------------------------------


def test_diff_compare_aussi_les_fichiers_de_niveau_depot(tmp_path, monkeypatch):
    """Sans cela, `forge diff` annoncerait « a jour » sur ce qu'il n'a pas regarde."""
    build_project(tmp_path)
    (tmp_path / "README.md").write_text("index reecrit\n", encoding="utf-8")

    result = _invoke(["diff", "-o", str(tmp_path)], monkeypatch)
    assert result.exit_code == 0, result.stdout
    assert "(racine)" in result.stdout
    assert "README.md" in result.stdout


# ---------------------------------------------------------------------------
# Filtres de plugin
# ---------------------------------------------------------------------------


def test_plugin_jinja_module_trouve_le_module_de_filtres_du_plugin():
    hooks = _manager().domain("demo")
    assert pipeline.plugin_jinja_module(hooks) == "forge.plugins.demo.jinja_ext"


def test_plugin_jinja_module_rend_vide_quand_le_plugin_n_en_fournit_pas():
    hooks = _manager(ISOLE).domain("isole")
    assert pipeline.plugin_jinja_module(hooks) == ""


# ---------------------------------------------------------------------------
# new : validation du filtre avant l'entretien
# ---------------------------------------------------------------------------


def test_new_refuse_un_domaine_inconnu_avant_de_poser_la_moindre_question(tmp_path, monkeypatch):
    """Sinon l'utilisateur repond a dix questions puis obtient un projet vide."""
    result = _invoke(
        ["new", "-o", str(tmp_path), "--only", "ansibel"], monkeypatch
    )
    assert result.exit_code == 1
    assert list(tmp_path.iterdir()) == []


# ---------------------------------------------------------------------------
# update : preuve qu'une evolution de gabarit arrive reellement dans la cible
# ---------------------------------------------------------------------------


def _git(cwd: Path, *args: str) -> None:
    """Commande git de test, avec une identite locale et les chemins longs actives.

    `core.longpaths` est indispensable sous Windows : les segments porteurs
    d'une balise `yield` allongent les chemins au-dela de la limite par defaut
    (MIGRATION.md §2.7).
    """
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=t@example.invalid",
            "-c",
            "user.name=test",
            "-c",
            "core.longpaths=true",
            *args,
        ],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


def _depot_de_gabarit(racine: Path) -> Path:
    """Copie minimale et versionnee du gabarit courant, isolee du depot forge.

    Copier le strict necessaire — le copier.yml racine et le gabarit du plugin
    demo — plutot que cloner le depot : le test reste ainsi valable meme quand
    l'arbre de travail porte des modifications non committees, c'est-a-dire
    precisement quand une regression d'update est possible.
    """
    gabarit = racine / "gabarit"
    sous_dossier = Path("src/forge/plugins/demo/template")
    (gabarit / sous_dossier).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(REPO_ROOT / "copier.yml", gabarit / "copier.yml")
    shutil.copytree(REPO_ROOT / sous_dossier, gabarit / sous_dossier)
    _git(gabarit, "init", "-q")
    _git(gabarit, "add", "-A")
    _git(gabarit, "commit", "-qm", "gabarit initial")
    return gabarit


@pytest.mark.integration
def test_update_applique_une_evolution_de_gabarit(tmp_path, monkeypatch):
    """Le coeur de `forge update` : une modification du gabarit doit arriver
    dans un projet deja livre. Sans cette assertion, on pouvait retirer
    entierement l'appel a copier sans qu'un test bronche."""
    gabarit = _depot_de_gabarit(tmp_path)
    cible = tmp_path / "projet"
    monkeypatch.setenv("FORGE_TEMPLATE_SRC", str(gabarit))
    monkeypatch.setenv("FORGE_PLUGINS", DEMO_PLUGIN)

    manager = _manager()
    data, model = load_case(SPECS_DIR / "demo-complet.yml", manager)
    pipeline.generate(data, model, manager, cible)

    livre = cible / "demo" / "README.md"
    assert "AJOUT DE LA VERSION 2" not in livre.read_text(encoding="utf-8")

    # La cible doit etre un depot git propre : copier fusionne a trois branches.
    _git(cible, "init", "-q")
    _git(cible, "add", "-A")
    _git(cible, "commit", "-qm", "projet initial")

    # Evolution du gabarit, committee : c'est ce que `forge update` doit apporter.
    source = gabarit / "src/forge/plugins/demo/template/README.md.jinja"
    source.write_text(
        source.read_text(encoding="utf-8") + "\nAJOUT DE LA VERSION 2\n",
        encoding="utf-8",
        newline="\n",
    )
    _git(gabarit, "commit", "-qam", "gabarit version 2")

    assert pipeline.update(manager, cible) == ["demo"]
    assert "AJOUT DE LA VERSION 2" in livre.read_text(encoding="utf-8")


@pytest.mark.integration
def test_update_refuse_un_gabarit_deplace_sans_commit(tmp_path, monkeypatch):
    """Un projet venu d'un autre poste : forge corrige _src_path, puis s'arrete.

    Il ne peut pas committer a la place de l'utilisateur, et copier refuse un
    depot cible sale : le message doit donc dire quoi faire.
    """
    gabarit = _depot_de_gabarit(tmp_path)
    cible = tmp_path / "projet"
    monkeypatch.setenv("FORGE_TEMPLATE_SRC", str(gabarit))

    manager = _manager()
    data, model = load_case(SPECS_DIR / "demo-complet.yml", manager)
    pipeline.generate(data, model, manager, cible)

    _git(cible, "init", "-q")
    _git(cible, "add", "-A")
    _git(cible, "commit", "-qm", "projet initial")

    # Le projet est cense venir d'un autre poste : son gabarit pointe ailleurs.
    answers = cible / "demo" / ".copier-answers.yml"
    answers.write_text(
        re.sub(
            r"^_src_path:.*$",
            "_src_path: /home/alice/forge",
            answers.read_text(encoding="utf-8"),
            count=1,
            flags=re.MULTILINE,
        ),
        encoding="utf-8",
        newline="\n",
    )

    with pytest.raises(RenderError, match="committez"):
        pipeline.update(manager, cible)
    # La correction a bien ete ecrite : c'est ce que l'utilisateur doit committer.
    assert gabarit.as_posix() in answers.read_text(encoding="utf-8")
