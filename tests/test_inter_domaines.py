"""Ce que forge apporte quand deux domaines decrivent le meme service.

C'est la promesse du projet : une seule description, deux projets
d'infrastructure coherents entre eux. Ce module verifie que la coherence est
reellement constatee — et surtout qu'elle est constatee **sans que le coeur
sache** ce qu'est un role Ansible ou un chart Helm.

Aucun de ces constats n'est accessible a un domaine seul : c'est la raison
d'etre de la comparaison de projections (decision Q4).
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
from typer.testing import CliRunner

from forge import pipeline
from forge.cli import app
from forge.plugins_api.manager import BUILTIN_PLUGINS, ForgeManager
from forge.spec.assembly import validate_spec
from forge.spec.io import load_spec_data, save_spec
from forge.validate.consistency import FACET_VOCABULARY, compare_projections
from tests.conftest import REPO_ROOT

runner = CliRunner()

#: Specification demandant les deux domaines.
SPEC_DEUX = REPO_ROOT / "tests" / "specs" / "deux-domaines.yml"


def _manager() -> ForgeManager:
    instance = ForgeManager()
    for module in BUILTIN_PLUGINS:
        instance.register_module(module)
    return instance


def _projections(data: dict) -> dict:
    manager = _manager()
    spec = validate_spec(data, manager)
    return {
        nom: manager.domain(nom).projection(spec)
        for nom in spec.domain_names()
        if manager.domain(nom).projection(spec) is not None
    }


@pytest.fixture
def donnees() -> dict:
    return load_spec_data(SPEC_DEUX)


# ---------------------------------------------------------------------------
# Ce que les deux domaines declarent
# ---------------------------------------------------------------------------


def test_les_deux_domaines_sont_generes_depuis_une_seule_specification(tmp_path, donnees):
    manager = _manager()
    resultat = pipeline.generate(donnees, validate_spec(donnees, manager), manager, tmp_path)

    assert resultat.domains == ["ansible", "helm"]
    assert (tmp_path / "ansible" / "playbooks" / "site.yml").is_file()
    assert (tmp_path / "helm" / "charts" / "boutique" / "Chart.yaml").is_file()
    # Un seul forge.yml, un seul README d'index, a la racine.
    assert (tmp_path / "forge.yml").is_file()
    readme = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "`ansible/`" in readme and "`helm/`" in readme


def test_une_specification_coherente_ne_produit_aucun_constat(donnees):
    assert compare_projections(_projections(donnees)) == []


def test_les_facettes_des_deux_domaines_appartiennent_au_vocabulaire(donnees):
    """Le nom d'une facette est un espace de noms partage : hors vocabulaire,
    elle n'est comparee a personne."""
    declarees = {
        facette
        for projection in _projections(donnees).values()
        for facette in projection.facets
    }
    assert declarees <= set(FACET_VOCABULARY), (
        f"facettes hors vocabulaire : {sorted(declarees - set(FACET_VOCABULARY))}"
    )


def test_les_deux_sortes_d_hotes_ne_sont_pas_confondues(donnees):
    """Machines d'inventaire et hotes d'Ingress ne designent pas la meme chose.

    Les avoir tous deux nommes `hosts` faisait echouer `forge validate` sur une
    specification parfaitement coherente : c'est le premier defaut qu'a revele
    la rencontre de deux domaines reels.
    """
    projections = _projections(donnees)
    machines = projections["ansible"].facets["inventory_hosts"]
    domaines = projections["helm"].facets["ingress_hosts"]

    assert machines and domaines
    assert not set(machines) & set(domaines)
    assert all(nom.startswith("db-") for nom in machines)
    assert all("." in nom for nom in domaines)


# ---------------------------------------------------------------------------
# Ce que seule la comparaison peut voir
# ---------------------------------------------------------------------------


def test_un_environnement_deploye_mais_non_administre_est_signale(donnees):
    """Helm deploie en production, Ansible n'y declare aucune machine.

    Aucun des deux domaines ne peut le dire seul : Ansible ne sait pas que Helm
    existe, et Helm ne lit pas l'inventaire.
    """
    donnees = copy.deepcopy(donnees)
    del donnees["ansible"]["hosts"]["prod"]

    constats = compare_projections(_projections(donnees))
    assert [constat.level for constat in constats] == ["warning"]
    assert "prod" in constats[0].message
    assert "helm" in constats[0].message and "ansible" in constats[0].message
    assert constats[0].hint


def test_un_nom_de_service_divergent_serait_une_erreur(donnees):
    """Garde-fou : les deux domaines doivent nommer le meme service."""
    projections = _projections(donnees)
    projections["helm"] = type(projections["helm"])(
        service_name="autre-service",
        environments=projections["helm"].environments,
        labels=projections["helm"].labels,
        facets=projections["helm"].facets,
    )
    constats = compare_projections(projections)
    assert any(constat.level == "error" for constat in constats)
    assert any("service name" in constat.message for constat in constats)


# ---------------------------------------------------------------------------
# La CLI, de bout en bout
# ---------------------------------------------------------------------------


def _ecrire_spec(donnees: dict, cible: Path) -> Path:
    chemin = cible / "forge.yml"
    save_spec(donnees, chemin, sections=["ansible", "helm"])
    return chemin


def test_validate_sort_en_zero_sur_un_projet_a_deux_domaines(tmp_path, donnees):
    """Le cas nominal : deux domaines, aucune incoherence."""
    manager = _manager()
    pipeline.generate(donnees, validate_spec(donnees, manager), manager, tmp_path)

    resultat = runner.invoke(
        app, ["validate", "-o", str(tmp_path), "--skip-missing"]
    )
    assert resultat.exit_code == 0, resultat.stdout
    assert "no difference" in resultat.stdout


def test_diff_couvre_les_deux_domaines_et_la_racine(tmp_path, donnees):
    manager = _manager()
    pipeline.generate(donnees, validate_spec(donnees, manager), manager, tmp_path)

    resultat = runner.invoke(app, ["diff", "-o", str(tmp_path)])
    assert resultat.exit_code == 0, resultat.stdout
    for rubrique in ("(root)", "ansible", "helm"):
        assert rubrique in resultat.stdout


def test_only_ne_regenere_qu_un_domaine_et_laisse_l_autre_intact(tmp_path, donnees):
    """`--only` doit proteger le domaine exclu, y compris de ses propres traces."""
    manager = _manager()
    pipeline.generate(donnees, validate_spec(donnees, manager), manager, tmp_path)

    temoin = tmp_path / "helm" / "charts" / "boutique" / "Chart.yaml"
    marque = temoin.read_text(encoding="utf-8") + "\n# marque de non-regeneration\n"
    temoin.write_text(marque, encoding="utf-8", newline="\n")

    resultat = pipeline.generate(
        donnees,
        validate_spec(donnees, manager),
        manager,
        tmp_path,
        only=["ansible"],
        force=True,
        spec_path=tmp_path / "forge.yml",
    )
    assert resultat.domains == ["ansible"]
    assert temoin.read_text(encoding="utf-8") == marque, "helm/ a ete regenere"


def test_update_ne_touche_qu_au_domaine_demande(tmp_path, donnees):
    """`forge update --only` : le domaine exclu ne doit pas etre appele."""
    manager = _manager()
    pipeline.generate(donnees, validate_spec(donnees, manager), manager, tmp_path)

    appeles: list[str] = []

    def espion(**kwargs):
        appeles.append(Path(kwargs["dst"]).name)
        return kwargs["dst"]

    import pytest as _pytest

    with _pytest.MonkeyPatch.context() as patch:
        patch.setattr(pipeline.copier_runner, "run_update", espion)
        mis_a_jour = pipeline.update(manager, tmp_path, only=["helm"])

    assert mis_a_jour == ["helm"]
    assert appeles == ["helm"], "ansible/ n'aurait pas du etre appele"


# ---------------------------------------------------------------------------
# La preuve : les deux chaines d'outils reelles, sur une seule specification
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_les_deux_projets_passent_leurs_validateurs_reels(tmp_path, donnees):
    """La promesse du projet, verifiee de bout en bout.

    Une seule description du service produit deux projets d'infrastructure, et
    les deux passent leurs propres outils : `ansible-playbook --syntax-check`
    par environnement et `ansible-lint` d'un cote, `helm lint`, `helm template`
    et `kubeconform -strict` par environnement de l'autre. Neuf commandes
    externes, aucune connaissance de domaine dans le coeur.
    """
    from tests.conftest import require_tools

    require_tools(
        "ansible+helm", "ansible-playbook", "ansible-lint", "helm", "kubeconform"
    )

    manager = _manager()
    spec = validate_spec(donnees, manager)
    pipeline.generate(donnees, spec, manager, tmp_path)

    resultat = pipeline.validate(spec, manager, tmp_path)
    echecs = [check for rapport in resultat.reports for check in rapport.failures()]
    assert not echecs, (
        f"validateurs en echec : {', '.join(c.label for c in echecs)}\n"
        + "\n".join(c.detail for c in echecs)[:2000]
    )

    lances = [c.label for rapport in resultat.reports for c in rapport.checks]
    assert len(lances) == 9, f"9 commandes attendues, {len(lances)} lancees : {lances}"
    assert not [issue for issue in resultat.issues if issue.level == "error"]
