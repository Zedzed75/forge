"""Les domaines sont un **choix**, jamais un lot.

C'est la promesse centrale de l'outil : une seule description du service, et
l'utilisateur decide ce qu'il en tire. Un projet peut n'avoir besoin que d'un
chart Helm ; un autre, que de roles et de playbooks Ansible ; un troisieme, que
d'un socle Terraform. Produire plusieurs domaines a la fois est **un** usage
possible, pas l'usage normal.

Trois facons de choisir, toutes couvertes ici :

* une section absente de `forge.yml` ne genere rien ;
* `--only` restreint une execution a certains domaines ;
* l'entretien de `forge new` demande lesquels produire.

**Ce module est ecrit pour ne pas pouvoir deriver.** Rien n'y code en dur ni le
nombre de domaines ni leurs noms : tout est lu dans le registre de plugins. Un
domaine ajoute sans sa specification mono-domaine fait echouer
`test_chaque_domaine_livre_a_une_specification_mono_domaine`, et la promesse
reste donc verifiee sur *tous* les domaines livres, pas sur ceux dont on s'est
souvenu le jour ou on a ecrit le test.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from forge import pipeline
from forge.cli import app, run_new
from forge.errors import SpecValidationError
from forge.plugins_api.manager import BUILTIN_PLUGINS, ForgeManager
from forge.spec.assembly import validate_spec
from forge.spec.io import load_spec_data, save_spec
from tests.conftest import REPO_ROOT, SPECS_DIR
from tests.scripted_prompter import ScriptedPrompter

runner = CliRunner()

SPEC_DEUX = SPECS_DIR / "deux-domaines.yml"


def _manager() -> ForgeManager:
    instance = ForgeManager()
    for module in BUILTIN_PLUGINS:
        instance.register_module(module)
    return instance


#: Domaines livres, lus dans le registre. Aucun nom n'est ecrit en dur ici :
#: c'est ce qui rend ce module solidaire de la realite du produit.
DOMAINES: tuple[str, ...] = _manager().domain_names()

#: Sous-repertoire de sortie de chaque domaine, lu dans son `DomainInfo`.
OUTDIRS: dict[str, str] = {nom: _manager().domain(nom).info.outdir for nom in DOMAINES}

#: Une specification **mono-domaine** par domaine livre : le cas ou un projet
#: n'a besoin que de celui-la. Le test de completude ci-dessous interdit
#: d'ajouter un domaine sans ajouter le sien.
SPECS_MONO: dict[str, Path] = {
    "ansible": SPECS_DIR / "ansible-ci.yml",
    "helm": SPECS_DIR / "helm-complet.yml",
    "terraform": SPECS_DIR / "terraform-complet.yml",
    "monitoring": SPECS_DIR / "monitoring-complet.yml",
    "pipeline": SPECS_DIR / "pipeline-seul.yml",
}


def _generer(spec_path: Path, cible: Path, **kwargs) -> pipeline.GenerationResult:
    manager = _manager()
    data = load_spec_data(spec_path)
    return pipeline.generate(data, validate_spec(data, manager), manager, cible, **kwargs)


def _domaines_produits(cible: Path) -> set[str]:
    """Domaines dont la sortie existe reellement dans la cible.

    Derive du registre, jamais d'une liste ecrite ici : un domaine ajoute est
    surveille sans qu'on y pense.

    Un domaine dont la sortie **est** la racine du depot — le domaine
    `pipeline`, dont le fichier n'a de sens que la ou l'outil de CI le lit — n'a
    pas de sous-repertoire a chercher : on constate alors la presence d'au moins
    un des chemins qu'il annonce.
    """
    produits = {
        nom
        for nom, outdir in OUTDIRS.items()
        if outdir not in (".", "") and (cible / outdir).is_dir()
    }
    for nom, outdir in OUTDIRS.items():
        if outdir in (".", "") and _ecrit_a_la_racine(cible, nom):
            produits.add(nom)
    return produits


def _ecrit_a_la_racine(cible: Path, domaine: str) -> bool:
    """Vrai si le domaine racine a ecrit au moins un de ses fichiers.

    Les chemins sont ceux que le plugin annonce lui-meme, moins le fichier de
    reponses copier : celui-ci existe dans toute cible generee, quel que soit le
    domaine.
    """
    from forge.plugins.pipeline import tree as pipeline_tree

    if domaine != "pipeline":  # pragma: no cover - un seul domaine racine
        return False
    return (cible / pipeline_tree.GITHUB_WORKFLOW).is_file() or (
        cible / pipeline_tree.GITLAB_CONFIG
    ).is_file()


# ---------------------------------------------------------------------------
# Le catalogue de cas ne peut pas deriver
# ---------------------------------------------------------------------------


def test_chaque_domaine_livre_a_une_specification_mono_domaine():
    """Un domaine ajoute sans son cas mono-domaine fait echouer ce test.

    C'est le verrou qui rend tous les autres tests de ce module exhaustifs :
    ils sont parametres sur `SPECS_MONO`, et `SPECS_MONO` doit couvrir le
    registre.
    """
    manquants = sorted(set(DOMAINES) - set(SPECS_MONO))
    en_trop = sorted(set(SPECS_MONO) - set(DOMAINES))
    assert not manquants, (
        f"domaines livres sans specification mono-domaine : {manquants}. "
        "Ajoutez-en une a tests/specs/ et referencez-la dans SPECS_MONO : la "
        "promesse « les domaines sont un choix » doit etre verifiee sur chacun."
    )
    assert not en_trop, f"SPECS_MONO cite des domaines inconnus : {en_trop}"


@pytest.mark.parametrize("domaine", sorted(SPECS_MONO), ids=sorted(SPECS_MONO))
def test_la_specification_de_reference_ne_declare_bien_qu_un_domaine(domaine):
    """Garde-fou sur les donnees de test elles-memes."""
    data = load_spec_data(SPECS_MONO[domaine])
    declares = sorted(set(data) & set(DOMAINES))
    assert declares == [domaine], f"{SPECS_MONO[domaine].name} declare {declares}"


# ---------------------------------------------------------------------------
# 1. Une section absente ne genere rien
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("domaine", sorted(SPECS_MONO), ids=sorted(SPECS_MONO))
def test_un_domaine_seul_ne_produit_que_lui(domaine, tmp_path):
    """Le cas d'usage le plus courant : un projet n'a besoin que d'un domaine."""
    resultat = _generer(SPECS_MONO[domaine], tmp_path)
    assert resultat.domains == [domaine]
    assert _domaines_produits(tmp_path) == {domaine}


@pytest.mark.parametrize("domaine", sorted(SPECS_MONO), ids=sorted(SPECS_MONO))
def test_un_domaine_seul_produit_bien_des_fichiers(domaine, tmp_path):
    """« Ne produire que lui » ne doit pas vouloir dire « ne rien produire »."""
    _generer(SPECS_MONO[domaine], tmp_path)
    racine = tmp_path / OUTDIRS[domaine]
    fichiers = [chemin for chemin in racine.rglob("*") if chemin.is_file()]
    # Un domaine ecrivant a la racine partage celle-ci avec les fichiers de
    # niveau depot : on compte alors ce qu'il annonce, pas ce qui s'y trouve.
    attendu = 1 if OUTDIRS[domaine] in (".", "") else 5
    assert len(fichiers) > attendu, f"{domaine} : {len(fichiers)} fichier(s) seulement"


def test_une_specification_sans_aucun_domaine_le_dit_clairement(tmp_path):
    """Un projet vide sans explication n'est pas une reponse acceptable."""
    spec = tmp_path / "forge.yml"
    save_spec(
        {
            "forge_version": 1,
            "service": {
                "name": "nu",
                "description": "Service sans domaine",
                "owner": "Equipe",
                "environments": [{"name": "prod"}],
            },
        },
        spec,
        sections=[],
    )
    cible = tmp_path / "projet"
    resultat = runner.invoke(app, ["generate", "-s", str(spec), "-o", str(cible)])

    assert resultat.exit_code == 0
    assert "no domain" in resultat.stdout
    assert "available domains" in resultat.stdout
    # Tous les domaines livres sont proposes, pas seulement ceux d'alors.
    for nom in DOMAINES:
        assert nom in resultat.stdout
    assert _domaines_produits(cible) == set()


# ---------------------------------------------------------------------------
# 2. `--only` restreint une execution
# ---------------------------------------------------------------------------


def test_only_restreint_la_generation_a_un_domaine(tmp_path):
    resultat = _generer(SPEC_DEUX, tmp_path, only=["helm"])
    assert resultat.domains == ["helm"]
    assert _domaines_produits(tmp_path) == {"helm"}


def test_only_accepte_plusieurs_domaines(tmp_path):
    resultat = _generer(SPEC_DEUX, tmp_path, only=["ansible", "helm"])
    assert resultat.domains == ["ansible", "helm"]


@pytest.mark.parametrize("domaine", sorted(SPECS_MONO), ids=sorted(SPECS_MONO))
def test_only_ne_peut_pas_ajouter_un_domaine_absent_de_la_specification(
    domaine, tmp_path
):
    """`--only` restreint ; il n'ajoute jamais un domaine que la spec ne demande pas.

    Et il le dit : demander un domaine absent est une erreur nommee, pas une
    generation vide. Un silence laisserait croire que le domaine a ete produit.
    """
    autres = [nom for nom in DOMAINES if nom != domaine]
    with pytest.raises(SpecValidationError) as leve:
        _generer(SPECS_MONO[domaine], tmp_path, only=autres)

    message = str(leve.value)
    for absent in autres:
        assert absent in message
    assert domaine in message, "le message doit rappeler ce que la spec declare"
    assert _domaines_produits(tmp_path) == set()


# ---------------------------------------------------------------------------
# 3. L'entretien demande lesquels produire
# ---------------------------------------------------------------------------


#: Reponses du tronc commun de `forge new`, communes a tous les entretiens.
SERVICE_COMMUN: list = [
    "boutique",              # nom du service
    "Boutique en ligne",     # description
    "Equipe Plateforme",     # responsable
    "",                      # contact
    "prod",                  # environnements
    True,                    # un environnement de production ?
    "prod",                  # lequel
    "",                      # domaine DNS de prod
]


def test_l_entretien_permet_de_ne_retenir_que_helm(tmp_path):
    """L'utilisateur coche `helm` seul : aucun autre domaine ne doit sortir."""
    manager = _manager()
    prompter = ScriptedPrompter(
        SERVICE_COMMUN
        + [
            ["helm"],                # <- LE CHOIX : helm seul
            "1.36", "0.1.0", "1.0.0",
            "docker.io", "boutique", "appVersion",
            "per_env",
            "api", "deployment", ["service"], "8080",
            False,                   # ajouter un autre composant ?
            True, True,              # makefile, tests helm
        ]
    )
    resultat = run_new(tmp_path, manager, prompter, spec_out=tmp_path / "forge.yml")

    assert prompter.exhausted, f"reponses non consommees : {prompter.answers}"
    assert resultat.domains == ["helm"]
    assert _domaines_produits(tmp_path) == {"helm"}
    ecrite = load_spec_data(tmp_path / "forge.yml")
    assert set(ecrite) & set(DOMAINES) == {"helm"}


def test_l_entretien_permet_de_ne_retenir_que_terraform(tmp_path):
    """Meme promesse, sur un domaine qui n'a aucun ancetre legacy."""
    manager = _manager()
    prompter = ScriptedPrompter(
        SERVICE_COMMUN
        + [
            ["terraform"],           # <- LE CHOIX : terraform seul
            ["namespace", "quota"],  # familles de ressources
            "~> 1.9",                # contrainte de version
            "per_env",               # strategie de namespace
            "local",                 # backend d'etat
            "kubeconfig",            # authentification
            "~/.kube/config",        # chemin du kubeconfig
            True,                    # un contexte par environnement
            True,                    # makefile
            True,                    # .tflint.hcl
        ]
    )
    resultat = run_new(tmp_path, manager, prompter, spec_out=tmp_path / "forge.yml")

    assert prompter.exhausted, f"reponses non consommees : {prompter.answers}"
    assert resultat.domains == ["terraform"]
    assert _domaines_produits(tmp_path) == {"terraform"}
    ecrite = load_spec_data(tmp_path / "forge.yml")
    assert set(ecrite) & set(DOMAINES) == {"terraform"}


# ---------------------------------------------------------------------------
# La CLI doit dire ce qu'elle fait
# ---------------------------------------------------------------------------


def test_generate_annonce_ce_qu_il_va_produire(tmp_path):
    resultat = runner.invoke(
        app,
        ["generate", "-s", str(SPEC_DEUX), "-o", str(tmp_path), "--only", "helm", "--dry-run"],
    )
    assert resultat.exit_code == 0, resultat.stdout
    assert "helm/" in resultat.stdout
    assert "ansible/" not in resultat.stdout


@pytest.mark.parametrize("domaine", sorted(SPECS_MONO), ids=sorted(SPECS_MONO))
def test_plugins_distingue_les_domaines_demandes_des_autres(domaine):
    """Le decompte est lu dans le registre : il ne peut pas se perimer."""
    resultat = runner.invoke(app, ["plugins", "-s", str(SPECS_MONO[domaine])])
    assert resultat.exit_code == 0, resultat.stdout
    lignes = resultat.stdout.splitlines()

    ligne_demande = next(ligne for ligne in lignes if ligne.startswith(domaine))
    assert "requested by the specification" in ligne_demande

    for autre in DOMAINES:
        if autre == domaine:
            continue
        ligne = next(ligne for ligne in lignes if ligne.startswith(autre))
        assert "not requested" in ligne, f"{autre} : {ligne}"

    assert f"1 domain(s) requested out of {len(DOMAINES)}" in resultat.stdout


@pytest.mark.parametrize(
    "spec",
    sorted(SPECS_MONO.values()) + [SPEC_DEUX],
    ids=sorted(SPECS_MONO) + ["deux"],
)
def test_validate_accepte_un_projet_mono_comme_multi_domaine(spec, tmp_path):
    """Aucun controle inter-domaines ne doit penaliser un projet a un domaine."""
    _generer(spec, tmp_path)
    resultat = runner.invoke(app, ["validate", "-o", str(tmp_path), "--skip-missing"])
    assert resultat.exit_code == 0, resultat.stdout
    assert "no difference" in resultat.stdout


@pytest.mark.parametrize("domaine", sorted(SPECS_MONO), ids=sorted(SPECS_MONO))
def test_diff_ne_voit_aucun_ecart_sur_un_projet_mono_domaine(domaine, tmp_path):
    """Un projet mono-domaine fraichement genere est a jour, par definition."""
    _generer(SPECS_MONO[domaine], tmp_path)
    resultat = runner.invoke(
        app, ["diff", "-o", str(tmp_path), "-s", str(SPECS_MONO[domaine])]
    )
    assert resultat.exit_code == 0, resultat.stdout
    assert "up to date" in resultat.stdout


# ---------------------------------------------------------------------------
# Les exemples livres sont des specifications valides
# ---------------------------------------------------------------------------

EXAMPLES_DIR = REPO_ROOT / "examples"


def _exemples() -> list[Path]:
    return sorted(EXAMPLES_DIR.glob("*.yml"))


def test_des_exemples_mono_domaine_sont_livres():
    """Un utilisateur doit trouver, dans le depot, un cas par domaine."""
    couverts = {
        nom
        for chemin in _exemples()
        for nom in set(load_spec_data(chemin)) & set(DOMAINES)
        if len(set(load_spec_data(chemin)) & set(DOMAINES)) == 1
    }
    assert couverts == set(DOMAINES), (
        f"exemples mono-domaine manquants pour : {sorted(set(DOMAINES) - couverts)}"
    )


@pytest.mark.parametrize(
    "exemple", _exemples(), ids=[chemin.stem for chemin in _exemples()]
)
def test_chaque_exemple_est_valide_et_se_genere(exemple, tmp_path):
    """Un exemple qui ne se genere pas est pire qu'aucun exemple."""
    resultat = _generer(exemple, tmp_path)
    demandes = sorted(set(load_spec_data(exemple)) & set(DOMAINES))
    assert resultat.domains == demandes
    assert _domaines_produits(tmp_path) == set(demandes)
