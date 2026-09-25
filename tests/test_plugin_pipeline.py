"""Domaine pipeline — celui dont la sortie depend des autres sections.

Le seul domaine du projet qui lit ce que les autres declarent. Toute la question
est de savoir **comment** : il ne doit connaitre aucun domaine par son nom, et
recevoir du coeur des faits dans le vocabulaire du contrat — `DomainInfo`,
`Command`, `Projection`.

Le temoin de cette promesse est `tests/domaines_factices/inconnu.py` : un domaine
que le plugin n'a jamais vu, avec un outil que sa table d'installation ne
connait pas. S'il en engendre un job correct sans qu'une ligne change, la
promesse tient ; sinon elle tenait par accident.

Ce module verrouille aussi les trois defauts trouves avant la mise de cote de la
phase 8, chacun par un test qui echouerait s'ils revenaient.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from forge import pipeline as pipeline_module
from forge.plugins.pipeline import answers, jobs, tools, tree, validators
from forge.plugins.pipeline.spec import PipelineSpec
from forge.plugins_api.manager import BUILTIN_PLUGINS, ForgeManager
from forge.spec.assembly import validate_spec
from forge.spec.io import load_spec_data
from tests.conftest import SPECS_DIR
from tests.domaines_factices.inconnu import OUTIL_INCONNU

SPEC_GITHUB = SPECS_DIR / "pipeline-github.yml"
SPEC_GITLAB = SPECS_DIR / "pipeline-seul.yml"

#: Domaine factice que le plugin pipeline n'a jamais vu.
PLUGIN_INCONNU = "tests.domaines_factices.inconnu"


def _manager(*extras: str) -> ForgeManager:
    instance = ForgeManager()
    for module in (*BUILTIN_PLUGINS, *extras):
        instance.register_module(module)
    return instance


def _spec(chemin: Path = SPEC_GITHUB, *extras: str):
    manager = _manager(*extras)
    data = load_spec_data(chemin)
    return data, validate_spec(data, manager), manager


def _base(**pipeline) -> dict:
    return {
        "forge_version": 1,
        "service": {
            "name": "boutique",
            "description": "Boutique en ligne",
            "owner": "Equipe",
            "environments": [{"name": "dev"}, {"name": "prod", "production": True}],
        },
        "pipeline": pipeline or {"provider": "github"},
    }


def _genere(tmp_path: Path, chemin: Path = SPEC_GITHUB, *extras: str):
    data, spec, manager = _spec(chemin, *extras)
    pipeline_module.generate(data, spec, manager, tmp_path)
    return spec, manager


def _projection(donnees: dict, *extras: str) -> dict:
    manager = _manager(*extras)
    spec = validate_spec(donnees, manager)
    return manager.domain("pipeline").answers(spec)


def _issues(donnees: dict, level: str) -> list[str]:
    spec = validate_spec(donnees, _manager())
    return [issue.message for issue in answers.cross_check(spec) if issue.level == level]


# ---------------------------------------------------------------------------
# La promesse : federer sans connaitre
# ---------------------------------------------------------------------------


def test_un_domaine_jamais_vu_obtient_son_job_de_validation():
    """Le temoin de la phase 8, et le seul test qui prouve vraiment la promesse.

    `inconnu` n'existait pas quand le plugin pipeline a ete ecrit. S'il obtient
    un job correct sans qu'une ligne change, c'est que le pipeline lit le
    contexte et non une liste de domaines connus.
    """
    donnees = _base(provider="github")
    donnees["inconnu"] = {"enabled": True}
    projection = _projection(donnees, PLUGIN_INCONNU)

    cles = [job["key"] for job in projection["validate_jobs"]]
    assert "valider-inconnu" in cles

    job = next(j for j in projection["jobs"] if j["key"] == "valider-inconnu")
    assert job["name"] == "Valider Domaine Inconnu"
    libelles = [etape["name"] for etape in job["steps"]]
    assert "rendu inconnu" in libelles and "controle inconnu" in libelles


def test_un_outil_inconnu_n_est_jamais_devine():
    """Le pipeline nomme ce qu'il ne sait pas installer, et fait echouer l'etape.

    Une etape muette laisserait le job tomber plus loin sur un « command not
    found », a l'endroit ou la cause n'est plus visible.
    """
    donnees = _base(provider="github")
    donnees["inconnu"] = {"enabled": True}
    projection = _projection(donnees, PLUGIN_INCONNU)

    assert OUTIL_INCONNU in projection["unknown_tools"]
    job = next(j for j in projection["jobs"] if j["key"] == "valider-inconnu")
    installation = job["steps"][0]
    assert OUTIL_INCONNU in " ".join(installation["run"])
    assert "exit 1" in installation["run"]


def test_un_domaine_muet_sur_le_deploiement_est_nomme_et_non_devine():
    """forge n'invente pas une commande de deploiement : il dit qui se tait."""
    _, spec, manager = _spec(SPEC_GITHUB)
    projection = manager.domain("pipeline").answers(spec)
    # Le cas de reference declare helm et terraform, qui savent se deployer.
    assert projection["undeployed"] == []
    assert projection["deploy_jobs"], "les domaines qui savent se deployer doivent l'avoir fait"


def test_le_pipeline_ne_se_declare_jamais_lui_meme_non_deploye():
    """Un pipeline ne se deploie pas : il est le deploiement."""
    donnees = _base(provider="github", deploy={"environments": ["dev"]})
    projection = _projection(donnees)
    assert "pipeline" not in projection["undeployed"]


# ---------------------------------------------------------------------------
# Les trois defauts trouves avant la mise de cote
# ---------------------------------------------------------------------------


def test_aucun_chemin_du_poste_n_entre_dans_le_pipeline(monkeypatch):
    """Defaut 1 : `Command.env` porte des chemins calcules sur la machine.

    Les recopier graverait le chemin d'un poste de developpement dans un fichier
    de CI, et rendrait la sortie **dependante de la machine qui l'a engendree** —
    un fichier golden ne pourrait plus etre compare.
    """
    monkeypatch.setenv("FORGE_ANSIBLE_COLLECTIONS", "/chemin/du/poste/collections")
    donnees = _base(provider="github")
    donnees["inconnu"] = {"enabled": True}
    projection = _projection(donnees, PLUGIN_INCONNU)

    rendu = json.dumps(projection)
    assert "/chemin/du/poste" not in rendu
    assert "/opt/quelque-part" not in rendu, "le chemin declare par `inconnu` doit tomber"
    # Ce qui reste est du reglage de comportement, valable partout.
    job = next(j for j in projection["jobs"] if j["key"] == "valider-inconnu")
    assert job["steps"][1]["env"] == {"NO_COLOR": "1"}


def test_la_projection_ne_depend_pas_de_l_environnement_du_processus(monkeypatch):
    """Corollaire du defaut 1, verifie sur la sortie complete."""
    donnees = _base(provider="github")
    donnees["inconnu"] = {"enabled": True}

    monkeypatch.delenv("FORGE_ANSIBLE_COLLECTIONS", raising=False)
    sans = json.dumps(_projection(donnees, PLUGIN_INCONNU), sort_keys=True)
    monkeypatch.setenv("FORGE_ANSIBLE_COLLECTIONS", "/ailleurs")
    monkeypatch.setenv("FORGE_TF_PLUGIN_CACHE", "/ailleurs/encore")
    avec = json.dumps(_projection(donnees, PLUGIN_INCONNU), sort_keys=True)
    assert sans == avec


def test_le_deploiement_suit_le_rang_declare_et_non_l_alphabet():
    """Defaut 2 : le chart partait avant le Terraform qui cree son namespace.

    Aucun tri generique ne pouvait le deviner : c'est une propriete du domaine,
    et `DomainInfo.deploy_order` la porte.
    """
    _, spec, manager = _spec(SPEC_GITHUB)
    projection = manager.domain("pipeline").answers(spec)
    job = projection["deploy_jobs"][0]
    repertoires = [etape["workdir"] for etape in job["steps"] if etape["workdir"]]
    premier_terraform = next(i for i, d in enumerate(repertoires) if d.startswith("terraform"))
    premier_helm = next(i for i, d in enumerate(repertoires) if d.startswith("helm"))
    assert premier_terraform < premier_helm, (
        "le socle doit partir avant ce qui s'y pose ; l'ordre alphabetique donnerait "
        "l'inverse"
    )


def test_le_chainage_stdin_devient_une_redirection_par_fichier():
    """Defaut 3 : un tube masquerait l'echec de la source.

    `pipefail` n'existe pas dans le `/bin/sh` d'une image Debian : la source
    ecrit dans un fichier, le consommateur le relit, et chaque etape porte son
    propre code de sortie.
    """
    donnees = _base(provider="gitlab")
    donnees["inconnu"] = {"enabled": True}
    projection = _projection(donnees, PLUGIN_INCONNU)

    job = next(j for j in projection["jobs"] if j["key"] == "valider-inconnu")
    lignes = [ligne for etape in job["steps"] for ligne in etape["run"]]
    source = next(ligne for ligne in lignes if "render" in ligne)
    consommateur = next(ligne for ligne in lignes if "check" in ligne)

    assert "|" not in source and "|" not in consommateur
    fichier = source.split("> ", 1)[1]
    assert consommateur.endswith(f"< {fichier}")


# ---------------------------------------------------------------------------
# Ce que le sous-modele refuse, et ce que le controle croise signale
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("provider", "runner"), [("github", "ubuntu-latest"), ("gitlab", "debian:trixie-slim")]
)
def test_le_runner_par_defaut_depend_de_l_outil(provider, runner):
    """GitHub nomme une machine, GitLab une image : pas le meme defaut."""
    assert PipelineSpec(provider=provider).runner == runner


def test_une_branche_repetee_est_refusee():
    with pytest.raises(ValueError, match="branches"):
        PipelineSpec(trigger={"branches": ["main", "main"]})


def test_une_cle_inconnue_est_refusee():
    with pytest.raises(ValueError):
        PipelineSpec(providr="github")


def test_l_ordre_de_deploiement_vient_du_bloc_partage():
    """La promotion dev -> prod est une propriete du service, pas du pipeline."""
    spec = PipelineSpec(deploy={"environments": ["prod", "dev"]})
    assert spec.deployed_environments(("dev", "staging", "prod")) == ("dev", "prod")


def test_un_environnement_de_deploiement_inconnu_est_une_erreur():
    donnees = _base(provider="github", deploy={"environments": ["recette"]})
    assert any("recette" in message for message in _issues(donnees, "error"))


def test_une_production_deployee_sans_garde_est_signalee():
    donnees = _base(
        provider="github",
        deploy={"environments": ["prod"], "manual_for_production": False},
    )
    assert any("sans approbation humaine" in m for m in _issues(donnees, "warning"))


def test_un_registre_que_le_jeton_n_ouvre_pas_est_signale():
    """forge ne peut ni deviner ni ecrire un secret de registre."""
    donnees = _base(provider="github", build={"registry": "registry.example.net"})
    assert any("n'ouvre pas" in message for message in _issues(donnees, "warning"))


def test_le_registre_par_defaut_ne_declenche_rien():
    donnees = _base(provider="github", build={"registry": "ghcr.io"})
    assert not any("n'ouvre pas" in message for message in _issues(donnees, "warning"))


def test_le_controle_croise_est_muet_sans_section_pipeline():
    class Sans:
        pass

    assert answers.cross_check(Sans()) == []


# ---------------------------------------------------------------------------
# Rendu
# ---------------------------------------------------------------------------


def test_l_arborescence_annoncee_correspond_aux_fichiers_generes(tmp_path):
    """Arbitrage R3, applique au seul domaine dont la sortie est la racine."""
    spec, _ = _genere(tmp_path)
    produits = {
        chemin.relative_to(tmp_path).as_posix()
        for chemin in tmp_path.rglob("*")
        if chemin.is_file()
    }
    assert set(tree.expected_paths(spec)) <= produits


def test_le_domaine_racine_n_ecrit_aucun_fichier_de_niveau_depot(tmp_path):
    """Il partage sa racine avec `README.md`, `forge.yml` et `.gitattributes`.

    En ecrire un les ecraserait, ou ferait echouer la generation sans `--force`.
    """
    spec, _ = _genere(tmp_path)
    annonces = set(tree.expected_paths(spec))
    assert not (annonces & tree.REPO_LEVEL_FILES)


@pytest.mark.parametrize(
    ("chemin", "attendu", "absent"),
    [
        (SPEC_GITHUB, tree.GITHUB_WORKFLOW, tree.GITLAB_CONFIG),
        (SPEC_GITLAB, tree.GITLAB_CONFIG, tree.GITHUB_WORKFLOW),
    ],
    ids=["github", "gitlab"],
)
def test_seul_le_dialecte_demande_est_ecrit(chemin, attendu, absent, tmp_path):
    _genere(tmp_path, chemin)
    assert (tmp_path / attendu).is_file()
    assert not (tmp_path / absent).exists()


@pytest.mark.parametrize("chemin", [SPEC_GITHUB, SPEC_GITLAB], ids=["github", "gitlab"])
def test_le_fichier_engendre_est_un_yaml_valide(chemin, tmp_path):
    spec, _ = _genere(tmp_path, chemin)
    contenu = (tmp_path / tree.workflow_path(spec)).read_bytes().decode("utf-8")
    document = yaml.safe_load(contenu)
    assert isinstance(document, dict) and document


def test_les_dependances_entre_jobs_designent_des_jobs_existants(tmp_path):
    """Un `needs` pendant est accepte par le fichier et refuse par l'outil."""
    _, spec, manager = _spec(SPEC_GITHUB)
    projection = manager.domain("pipeline").answers(spec)
    cles = {job["key"] for job in projection["jobs"]}
    for job in projection["jobs"]:
        assert set(job["needs"]) <= cles, job["key"]


def test_le_tag_d_image_est_l_empreinte_du_commit(tmp_path):
    """Jamais `latest` : deux constructions du meme `latest` sont deux images."""
    _, spec, manager = _spec(SPEC_GITHUB)
    projection = manager.domain("pipeline").answers(spec)
    etape = projection["build_job"]["steps"][0]
    assert etape["env"]["FORGE_IMAGE_TAG"] == "${{ github.sha }}"
    assert ":latest" not in " ".join(etape["run"])


def test_aucun_identifiant_n_est_ecrit_dans_le_fichier_engendre(tmp_path):
    spec, _ = _genere(tmp_path)
    contenu = (tmp_path / tree.workflow_path(spec)).read_bytes().decode("utf-8")
    for motif in ("password:", "token:", "secret_key", "BEGIN "):
        assert motif not in contenu


def test_diff_ne_voit_aucun_ecart_juste_apres_generation(tmp_path):
    """Exerce `foreign_paths` : un domaine racine ne compare pas ce qui n'est pas a lui."""
    data, spec, manager = _spec(SPEC_GITHUB)
    pipeline_module.generate(data, spec, manager, tmp_path)
    ecarts = pipeline_module.diff(
        data, spec, manager, tmp_path, only=["pipeline"], spec_path=tmp_path / "forge.yml"
    )
    for ecart in ecarts:
        assert ecart.empty, ecart.summary()


# ---------------------------------------------------------------------------
# Table d'installation et validateurs
# ---------------------------------------------------------------------------


def test_chaque_outil_declare_par_un_domaine_livre_est_installable():
    """Un outil que le pipeline ne sait pas installer rend son job inutilisable."""
    manager = _manager()
    manquants: set[str] = set()
    for chemin in sorted(SPECS_DIR.glob("*.yml")):
        data = load_spec_data(chemin)
        if not (set(data) & set(manager.domain_names())):
            continue
        spec = validate_spec(data, manager)
        for nom in manager.domain_names():
            if getattr(spec, nom, None) is None:
                continue
            for commande in manager.domain(nom).validators(spec, Path(nom)):
                if not tools.known(commande.tool):
                    manquants.add(f"{nom}:{commande.tool}")
    assert manquants == set(), f"outils sans recette d'installation : {sorted(manquants)}"


def test_les_versions_des_outils_sont_figees():
    """« La derniere version » change de comportement un matin sans commit."""
    for recette in tools.INSTALLS:
        for ligne in recette.steps:
            assert "latest/download" not in ligne, recette.name


# ---------------------------------------------------------------------------
# Ce qu'un domaine publie, le pipeline l'installe sans le connaitre
# ---------------------------------------------------------------------------


def _avec_ansible() -> dict:
    """Specification minimale ou le pipeline rencontre le domaine Ansible.

    Aucun cas de reference ne reunit les deux — c'est d'ailleurs pourquoi le
    defaut de ZED-8 a survecu a huit phases : la table du pipeline recopiait
    trois collections sans version, et aucun golden ne montrait la ligne.
    """
    donnees = _base(provider="github")
    donnees["ansible"] = {
        "os_family": "debian",
        "groups": [
            {
                "name": "bases",
                "description": "Bases de donnees",
                "roles": ["common", "postgresql"],
            }
        ],
        "hosts": {"prod": {"bases": [{"name": "db-01", "ansible_host": "10.0.0.1"}]}},
    }
    return donnees


def _etape_d_installation(donnees: dict, cle: str) -> list[str]:
    """Lignes de shell de l'etape « Installer les outils » du job `cle`."""
    projection = _projection(donnees)
    job = next(j for j in projection["jobs"] if j["key"] == cle)
    etape = next(e for e in job["steps"] if e["name"] == "Installer les outils")
    return etape["run"]


def test_le_pipeline_installe_les_collections_que_le_domaine_publie():
    """La liste n'est plus recopiee : elle vient de la projection du domaine.

    Le pipeline ne connait ni le nom des collections ni leur version — il lit
    une facette et recopie des chaines opaques. C'est ce qui permet a la table
    de `catalog/collections.py` de rester le seul endroit ou une version de
    collection est autorisee (DESIGN.md §8 Q10).
    """
    donnees = _avec_ansible()
    spec = validate_spec(donnees, _manager())
    publiees = _manager().context(spec).get("ansible").projection.facets[
        "galaxy_collections"
    ]

    lignes = _etape_d_installation(donnees, "valider-ansible")
    galaxy = [ligne for ligne in lignes if "ansible-galaxy" in ligne]
    assert len(galaxy) == 1, lignes
    for publiee in publiees:
        assert publiee in galaxy[0], publiee


def test_aucune_collection_n_est_installee_sans_version():
    """Le defaut exact de ZED-8 : `ansible-galaxy collection install <nom>` nu.

    Une collection sans contrainte installe ce que Galaxy sert ce jour-la, et le
    pipeline genere change de verdict un matin sans qu'une ligne du depot ait
    bouge — ce que `community.postgresql` 5.0.0 a deja fait.
    """
    lignes = _etape_d_installation(_avec_ansible(), "valider-ansible")
    galaxy = next(ligne for ligne in lignes if "ansible-galaxy" in ligne)
    for morceau in galaxy.split():
        if "." in morceau and not morceau.startswith("-") and "/" not in morceau:
            assert ":" in morceau, f"collection sans version : {morceau}"


def test_les_outils_ansible_du_pipeline_sont_epingles():
    """`pip install ansible-core` tout nu etait la seconde moitie du defaut."""
    lignes = _etape_d_installation(_avec_ansible(), "valider-ansible")
    pips = [ligne for ligne in lignes if "pip install" in ligne]
    assert pips
    for ligne in pips:
        assert "==" in ligne, ligne


def test_une_facette_absente_n_installe_rien_de_devine():
    """Un domaine tiers peut declarer `ansible-playbook` sans rien publier.

    L'installation se reduit alors a l'outil lui-meme : le pipeline n'invente
    pas une liste de dependances, et n'echoue pas non plus — un projet qui ne
    s'appuie que sur les modules livres n'a rien a installer.
    """
    etape, connus, inconnus = jobs.install_step(("ansible-playbook",), "github")
    assert connus == ["ansible-playbook"] and inconnus == []
    assert not any("ansible-galaxy" in ligne for ligne in etape.run)


@pytest.mark.parametrize(
    ("chemin", "outil"), [(SPEC_GITHUB, "actionlint"), (SPEC_GITLAB, "yamllint")], ids=["github", "gitlab"]
)
def test_le_validateur_depend_du_dialecte(chemin, outil, tmp_path):
    _, spec, _ = _spec(chemin)
    commandes = validators.commands(spec, tmp_path)
    assert [commande.tool for commande in commandes] == [outil]
    assert tree.workflow_path(spec) in commandes[0].argv


# ---------------------------------------------------------------------------
# Entretien
# ---------------------------------------------------------------------------


def test_l_entretien_produit_une_section_valide():
    from forge.plugins.pipeline import interview
    from tests.scripted_prompter import ScriptedPrompter

    service = validate_spec(_base(provider="github"), _manager()).service
    prompter = ScriptedPrompter(
        [
            "github",       # outil de CI
            "main",         # branche principale
            True,           # declencher sur les propositions de fusion
            True,           # construire une image
            "ghcr.io",      # registre
            "boutique",     # depot de l'image
            True,           # deployer
            ["dev"],        # environnements deployes
        ]
    )
    section = interview.run(prompter, service)
    assert prompter.exhausted, f"reponses non consommees : {prompter.answers}"
    modele = PipelineSpec.model_validate(section)
    assert modele.is_github
    assert modele.deployed_environments(("dev", "prod")) == ("dev",)


def test_l_entretien_se_limite_a_valider_si_aucun_environnement_n_est_retenu():
    from forge.plugins.pipeline import interview
    from tests.scripted_prompter import ScriptedPrompter

    service = validate_spec(_base(provider="github"), _manager()).service
    prompter = ScriptedPrompter(["github", "main", True, False, True, []])
    section = interview.run(prompter, service)
    assert prompter.exhausted
    assert "deploy" not in section


# ---------------------------------------------------------------------------
# Validation reelle du fichier engendre
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.parametrize(
    ("chemin", "outil"), [(SPEC_GITHUB, "actionlint"), (SPEC_GITLAB, "yamllint")], ids=["github", "gitlab"]
)
def test_le_pipeline_genere_passe_son_validateur(chemin, outil, tmp_path):
    """`actionlint` connait le schema des workflows GitHub, leurs expressions et
    leurs actions. Cote GitLab, il n'existe pas d'equivalent hors ligne : la
    garantie y est plus faible, et le README du domaine le dit."""
    from tests.conftest import require_tools

    require_tools("pipeline", outil)

    spec, manager = _genere(tmp_path, chemin)
    resultat = pipeline_module.validate(spec, manager, tmp_path, only=["pipeline"])
    echecs = [check for rapport in resultat.reports for check in rapport.failures()]
    assert not echecs, (
        f"validateurs en echec : {', '.join(c.label for c in echecs)}\n"
        + "\n".join(c.detail for c in echecs)[:2000]
    )


def test_toute_expansion_de_variable_est_protegee_par_des_guillemets():
    """shellcheck (SC2086) fait echouer actionlint sur une expansion nue.

    Trouve par la CI : shellcheck n'etait pas installe sur le poste, donc
    actionlint ne le lancait pas et l'etape passait. Ce n'est pas du zele — un
    tag contenant un blanc ou un caractere generique serait coupe en plusieurs
    arguments par le shell.
    """
    import re

    donnees = _base(provider="github", build={"registry": "ghcr.io", "image": "acme/x"})
    projection = _projection(donnees)
    nue = re.compile(r'(?<!")\$[A-Za-z_][A-Za-z0-9_]*')
    for job in projection["jobs"]:
        for etape in job["steps"]:
            for ligne in etape["run"]:
                # `2>/dev/null` et les expansions deja entre guillemets sont sures ;
                # on ne cherche que les `$VAR` que rien n'entoure.
                fautives = [
                    trouve.group(0)
                    for trouve in nue.finditer(ligne)
                    if f'"{trouve.group(0)}"' not in ligne
                    and f'"{trouve.group(0)}\\"' not in ligne
                    and not _dans_des_guillemets(ligne, trouve.start())
                ]
                assert not fautives, f"{job['key']} / {etape['name']} : {fautives}\n{ligne}"


def _dans_des_guillemets(ligne: str, position: int) -> bool:
    """Vrai si le caractere a `position` est a l'interieur d'une paire de `"`."""
    return ligne[:position].count('"') % 2 == 1
