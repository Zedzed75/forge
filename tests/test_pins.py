"""Les versions epinglees ne doivent jamais diverger en silence.

Trois machines installent les outils du domaine Ansible, et chacune a son
fichier : la CI de forge (`.github/workflows/ci.yml`), le workflow que le projet
genere emporte (`plugins/ansible/catalog/tooling.py`), et le pipeline engendre a
la racine du depot (`plugins/pipeline/tools.py`). La duplication est assumee —
un outil appartient au provisionnement d'une machine, et rien n'oblige deux
machines a en etre a la meme version — mais elle n'a de sens que si un ecart
devient visible le jour ou il est ecrit, et non six mois plus tard chez
l'utilisateur.

Ce module est ce garde-fou. Il lit les fichiers plutot que d'importer des
constantes : c'est le texte reellement livre qui doit s'accorder, pas une
variable qu'on aurait pu oublier de brancher.

Le pendant pour les **collections** n'existe pas ici, et c'est voulu : leur
version n'est ecrite qu'une seule fois (`plugins/ansible/catalog/collections.py`)
et voyage par la projection du domaine. Il n'y a rien a comparer.
"""

from __future__ import annotations

import re

import pytest

from forge.plugins.ansible.catalog import collections as catalog_collections
from forge.plugins.ansible.catalog import tooling
from forge.plugins.pipeline import tools
from tests.conftest import REPO_ROOT

#: Workflow de la CI de forge, lu tel quel.
CI_WORKFLOW = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

#: Source de la table d'installation du pipeline, lue telle quelle.
TOOLS_SOURCE = (
    REPO_ROOT / "src" / "forge" / "plugins" / "pipeline" / "tools.py"
).read_text(encoding="utf-8")


def _pin_ci(paquet: str) -> str:
    """Version a laquelle la CI de forge epingle `paquet` (`'nom==x.y.z'`)."""
    trouves = re.findall(rf"'{re.escape(paquet)}==([0-9][^']*)'", CI_WORKFLOW)
    assert trouves, f"la CI de forge n'epingle pas {paquet}"
    assert len(set(trouves)) == 1, f"{paquet} epingle a plusieurs versions : {trouves}"
    return trouves[0]


# ---------------------------------------------------------------------------
# Outils du domaine Ansible : trois fichiers, une seule version
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("paquet", "attendue"),
    [
        ("ansible-core", tooling.ANSIBLE_CORE),
        ("ansible-lint", tooling.ANSIBLE_LINT),
    ],
)
def test_la_ci_de_forge_valide_contre_la_version_que_le_projet_genere_installe(
    paquet, attendue
):
    """Sinon forge livre un projet valide contre autre chose que ce qu'il installe.

    L'ecart est silencieux par nature : la CI de forge reste verte, le projet
    genere passe au rouge chez son proprietaire, et rien dans les deux depots ne
    dit pourquoi.
    """
    assert _pin_ci(paquet) == attendue


@pytest.mark.parametrize(
    ("paquet", "attendue"),
    [
        ("ansible-core", tooling.ANSIBLE_CORE),
        ("ansible-lint", tooling.ANSIBLE_LINT),
    ],
)
def test_le_pipeline_installe_la_version_que_le_domaine_annonce(paquet, attendue):
    """Le pipeline engendre valide la meme sortie que la CI du projet Ansible.

    Deux verdicts contradictoires sur le meme depot, rendus par deux fichiers
    que forge ecrit tous les deux, seraient le plus couteux des defauts a
    diagnostiquer.
    """
    assert tools.VERSIONS[paquet] == attendue


def test_le_pipeline_installe_le_yamllint_de_la_ci():
    """Meme regle pour l'outil du dialecte GitLab, dont le pipeline depend."""
    assert tools.VERSIONS["yamllint"] == _pin_ci("yamllint")


# ---------------------------------------------------------------------------
# Collections : une seule table, et le pipeline ne la recopie pas
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "besoin",
    catalog_collections.COLLECTION_REQUIREMENTS.values(),
    ids=lambda besoin: besoin.name,
)
def test_la_ci_installe_la_version_contre_laquelle_le_catalogue_dit_valider(besoin):
    """`CollectionRequirement.validated` est une affirmation verifiable.

    Le fichier genere la cite mot pour mot (« la majeure suivant la 5.0.0,
    version contre laquelle forge valide les projets generes »). Si la CI
    installe autre chose, ce commentaire ment a l'utilisateur.
    """
    attendu = f"{besoin.name}:{besoin.validated}"
    assert attendu in CI_WORKFLOW, f"la CI de forge n'installe pas {attendu}"


@pytest.mark.parametrize(
    "nom", sorted(catalog_collections.COLLECTION_REQUIREMENTS), ids=lambda nom: nom
)
def test_la_table_du_pipeline_ne_nomme_aucune_collection(nom):
    """La regle de ZED-7, etendue au pipeline : une collection, un seul auteur.

    `plugins/pipeline/tools.py` recopiait les trois noms, sans version. Elles
    lui parviennent desormais par la projection du domaine qui les declare ; les
    voir reapparaitre dans cette source serait le retour exact du defaut.
    """
    assert nom not in TOOLS_SOURCE


# ---------------------------------------------------------------------------
# Aucune etape d'installation sans version
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("recette", tools.INSTALLS, ids=lambda recette: recette.name)
def test_chaque_recette_cite_une_version_figee(recette):
    """« La derniere version » change de comportement un matin sans commit.

    Le critere est grossier a dessein : une recette doit citer au moins un
    numero de la table des versions. Il suffit a refuser l'etape qu'on ajoute
    sans y penser — `pip install <outil>` tout nu, qui est exactement la forme
    sous laquelle les deux outils Ansible ont echappe a la regle pendant huit
    phases.
    """
    texte = " ".join(recette.steps)
    assert any(version in texte for version in tools.VERSIONS.values()), (
        f"aucune version figee dans l'installation de {recette.name} : {texte}"
    )


def test_les_dependances_d_une_facette_ne_sont_pas_epinglees_ici():
    """Ce qu'une recette recoit d'un domaine, elle ne doit pas le figer elle-meme.

    La ligne porte `{items}` et rien d'autre : le jour ou quelqu'un y ecrit une
    version, il a recree la seconde source de verite que cette facette existe
    pour supprimer.
    """
    for recette in tools.INSTALLS:
        if recette.from_facet is None:
            continue
        assert "{items}" in recette.from_facet.line, recette.name
        assert not re.search(r"[=<>]=?\s*[0-9]", recette.from_facet.line), recette.name
