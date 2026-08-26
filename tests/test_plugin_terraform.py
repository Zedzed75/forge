"""Domaine Terraform — le premier ecrit de zero.

Aucun generateur legacy a porter, donc **aucun instantane de parite** : rien ne
dit « la sortie est juste » a part ce module et les outils reels. La couverture
est donc organisee autrement que celle des deux autres domaines :

* ce que le **modele** refuse (contraintes que Terraform ne signalerait qu'au
  `init`, c'est-a-dire trop tard) ;
* ce que le **controle croise** refuse ou signale ;
* la **coherence interne** de la projection — catalogue, variables, sorties et
  gabarits doivent parler des memes noms ;
* l'**absence de valeur secrete** dans tout fichier genere ;
* et, sous marqueur `integration`, les **validateurs reels** : `terraform fmt`,
  `terraform init`, `terraform validate` et `tflint`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from forge import pipeline
from forge.plugins.terraform import answers, derive, tree, validators
from forge.plugins.terraform.catalog.families import FAMILIES
from forge.plugins.terraform.catalog.registry import family_names
from forge.plugins.terraform.enums import ResourceFamily
from forge.plugins.terraform.spec import TerraformSpec
from forge.plugins_api.manager import ForgeManager
from forge.spec.assembly import validate_spec
from forge.spec.io import load_spec_data
from tests.conftest import REPO_ROOT

PLUGIN = "forge.plugins.terraform.plugin"
SPEC_COMPLETE = REPO_ROOT / "tests" / "specs" / "terraform-complet.yml"


def _manager() -> ForgeManager:
    instance = ForgeManager()
    instance.register_module(PLUGIN)
    return instance


def _spec(donnees: dict | None = None):
    """Modele racine valide, a partir de la spec de reference ou d'un dict."""
    manager = _manager()
    data = donnees if donnees is not None else load_spec_data(SPEC_COMPLETE)
    return data, validate_spec(data, manager), manager


def _base(**terraform) -> dict:
    """Specification minimale, avec la section terraform fournie."""
    return {
        "forge_version": 1,
        "service": {
            "name": "boutique",
            "description": "Boutique en ligne",
            "owner": "Equipe",
            "environments": [{"name": "dev"}, {"name": "prod", "production": True}],
        },
        "terraform": terraform or {"resources": ["namespace"]},
    }


def _genere(tmp_path: Path, donnees: dict | None = None):
    data, spec, manager = _spec(donnees)
    pipeline.generate(data, spec, manager, tmp_path)
    return spec, manager


# ---------------------------------------------------------------------------
# Ce que le sous-modele refuse
# ---------------------------------------------------------------------------


def test_une_version_nue_est_refusee_comme_contrainte():
    """`1.9.8` figerait le projet sur un correctif : presque toujours une faute."""
    with pytest.raises(ValueError, match="contrainte de version"):
        TerraformSpec(terraform_version="1.9.8")


@pytest.mark.parametrize("contrainte", ["~> 1.9", ">= 1.5, < 2.0", "~> 1.9.0"])
def test_les_contraintes_bien_formees_passent(contrainte):
    assert TerraformSpec(terraform_version=contrainte).terraform_version == contrainte


def test_une_cle_de_backend_secrete_est_refusee():
    """Un fichier genere ne porte jamais de secret, backend compris."""
    with pytest.raises(ValueError, match="secretes refusees"):
        TerraformSpec(backend={"kind": "s3", "config": {"bucket": "b", "region": "r", "secret_key": "x"}})


def test_une_cle_de_backend_obligatoire_absente_est_refusee():
    """Sinon le projet se rend parfaitement et refuse de s'initialiser."""
    with pytest.raises(ValueError, match="cles obligatoires absentes"):
        TerraformSpec(backend={"kind": "s3", "config": {"bucket": "b"}})


def test_la_cle_d_etat_n_est_pas_reclamee_a_la_specification():
    """`key` est derivee par environnement : l'exiger produirait un etat partage."""
    spec = TerraformSpec(backend={"kind": "s3", "config": {"bucket": "b", "region": "r"}})
    assert "key" not in spec.backend.config


def test_une_famille_repetee_est_refusee():
    with pytest.raises(ValueError, match="familles de ressources"):
        TerraformSpec(resources=["namespace", "namespace"])


def test_la_strategie_custom_exige_un_namespace_par_environnement_declare():
    with pytest.raises(ValueError, match="custom"):
        TerraformSpec(namespace_strategy="custom", environments={"dev": {}})


def test_un_namespace_explicite_trop_long_est_refuse():
    with pytest.raises(ValueError, match="63"):
        TerraformSpec(environments={"dev": {"namespace": "n" * 64}})


def test_une_cle_inconnue_est_refusee():
    """`extra=\"forbid\"` : une faute de frappe n'est jamais un silence."""
    with pytest.raises(ValueError):
        TerraformSpec(terrraform_version="~> 1.9")


# ---------------------------------------------------------------------------
# Ce que le controle croise refuse ou signale
# ---------------------------------------------------------------------------


def _issues(donnees: dict) -> list:
    manager = _manager()
    spec = validate_spec(donnees, manager)
    return answers.cross_check(spec)


def _messages(donnees: dict, level: str) -> list[str]:
    return [issue.message for issue in _issues(donnees) if issue.level == level]


def test_un_environnement_inconnu_est_une_erreur():
    donnees = _base(resources=["namespace"], environments={"recette": {"namespace": "x"}})
    assert any("recette" in m for m in _messages(donnees, "error"))


def test_la_strategie_custom_couvre_tous_les_environnements_du_service():
    """Un environnement absent de `terraform.environments` echappe au sous-modele."""
    donnees = _base(
        resources=["namespace"],
        namespace_strategy="custom",
        environments={"dev": {"namespace": "boutique-dev"}},
    )
    erreurs = _messages(donnees, "error")
    assert any("prod" in m for m in erreurs)
    assert not any("'dev'" in m for m in erreurs)


def test_un_namespace_derive_trop_long_est_une_erreur():
    """Ni le service ni l'environnement ne depassent seuls : le produit, si."""
    donnees = _base(resources=["namespace"])
    donnees["service"]["name"] = "b" * 55
    donnees["service"]["environments"] = [{"name": "integration"}]
    assert any("63" in m for m in _messages(donnees, "error"))


def test_une_surcharge_sans_sa_famille_est_signalee():
    """Une valeur soigneusement reglee et ignoree en silence est pire qu'une erreur."""
    donnees = _base(
        resources=["namespace"],
        environments={"prod": {"quota": {"cpu": "8"}}},
    )
    avertissements = _messages(donnees, "warning")
    assert any("quota" in m and "ne sera pas appliquee" in m for m in avertissements)


def test_un_etat_local_en_production_est_signale():
    donnees = _base(resources=["namespace", "random_secret"])
    avertissements = _messages(donnees, "warning")
    assert any("backend d'etat 'local'" in m for m in avertissements)
    assert any("random_secret" in m for m in avertissements)


def test_un_contexte_de_cluster_absent_est_signale():
    donnees = _base(
        resources=["namespace"],
        kubernetes={"context_per_environment": False},
    )
    assert any("contexte courant" in m for m in _messages(donnees, "warning"))


def test_la_specification_de_reference_ne_leve_aucune_erreur():
    _, spec, _ = _spec()
    assert [issue for issue in answers.cross_check(spec) if issue.level == "error"] == []


def test_le_controle_croise_est_muet_sans_section_terraform():
    class Sans:
        pass

    assert answers.cross_check(Sans()) == []


# ---------------------------------------------------------------------------
# Coherence interne de la projection
# ---------------------------------------------------------------------------


def test_la_projection_est_serialisable_et_deterministe():
    _, spec, _ = _spec()
    premier = answers.build(spec)
    second = answers.build(spec)
    assert json.dumps(premier, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_toutes_les_familles_de_l_enumeration_sont_au_catalogue():
    assert set(family_names()) == {famille.value for famille in ResourceFamily}


def test_chaque_famille_documente_ses_pieges():
    """Les pieges expliquent des choix du code genere : aucune famille sans."""
    muettes = [famille.name for famille in FAMILIES if not famille.traps]
    assert muettes == [], f"familles sans piege documente : {muettes}"


def test_chaque_sortie_de_famille_a_une_expression():
    """Une sortie declaree sans expression ferait echouer le rendu, pas le test."""
    connues = set(derive.OUTPUT_VALUES)
    declarees = {nom for famille in FAMILIES for nom in famille.outputs}
    assert declarees <= connues


def test_les_familles_ne_reclament_que_des_providers_connus():
    _, spec, _ = _spec()
    noms = {provider["name"] for provider in derive.providers(spec)}
    assert noms == {"kubernetes", "random", "tls"}


def test_le_tfvars_ne_cite_que_des_variables_declarees():
    """Terraform refuse un tfvars citant une variable inconnue."""
    _, spec, _ = _spec()
    projection = answers.build(spec)
    declarees = {variable["name"] for variable in projection["root_variables"]}
    for env in projection["environments"]:
        cites = {entree["name"] for entree in env["tfvars"]}
        assert cites <= declarees, f"{env['name']} : {sorted(cites - declarees)}"


def test_le_tfvars_ne_porte_aucune_variable_secrete():
    _, spec, _ = _spec()
    projection = answers.build(spec)
    secretes = {v["name"] for v in projection["root_variables"] if v["sensitive"]}
    assert secretes, "le cas de reference doit exercer au moins une variable secrete"
    for env in projection["environments"]:
        assert not secretes & {entree["name"] for entree in env["tfvars"]}


def test_l_appel_de_module_transmet_toutes_ses_variables():
    """Terraform ne signale pas une variable declaree et jamais transmise."""
    _, spec, _ = _spec()
    projection = answers.build(spec)
    attendues = {variable["name"] for variable in projection["variables"]}
    for env in projection["environments"]:
        transmises = {argument["name"] for argument in env["module_arguments"]}
        assert transmises == attendues


def test_deux_environnements_n_ecrivent_jamais_le_meme_etat():
    _, spec, _ = _spec()
    projection = answers.build(spec)
    cles = [
        tuple(sorted((e["name"], e["value"]) for e in env["backend_config"]))
        for env in projection["environments"]
    ]
    assert len(set(cles)) == len(cles)


def test_les_namespaces_derives_suivent_la_strategie():
    _, spec, _ = _spec()
    projection = answers.build(spec)
    assert [env["namespace"] for env in projection["environments"]] == [
        "boutique-dev",
        "boutique-staging",
        "boutique-prod",
    ]


def test_la_facette_declaree_appartient_au_vocabulaire_partage():
    """Une facette hors vocabulaire est sans danger, mais sans effet (phase 5)."""
    from forge.plugins.terraform import plugin as terraform_plugin
    from forge.validate.consistency import FACET_VOCABULARY

    _, spec, _ = _spec()
    projection = terraform_plugin.forge_projection(spec)
    assert set(projection.facets) <= set(FACET_VOCABULARY)
    assert projection.facets["namespaces"] == (
        "boutique-dev",
        "boutique-prod",
        "boutique-staging",
    )


# ---------------------------------------------------------------------------
# Rendu
# ---------------------------------------------------------------------------


def test_l_arborescence_annoncee_correspond_aux_fichiers_generes(tmp_path):
    """Arbitrage R3 : `tree.py` reste au plugin, mais un test le tient a jour."""
    spec, _ = _genere(tmp_path)
    base = tmp_path / "terraform"
    produits = {
        chemin.relative_to(base).as_posix() for chemin in base.rglob("*") if chemin.is_file()
    }
    assert produits == set(tree.expected_paths(spec))


def test_chaque_famille_retenue_produit_son_fichier(tmp_path):
    spec, _ = _genere(tmp_path)
    module = tmp_path / "terraform" / "modules" / "boutique"
    for famille in FAMILIES:
        chemin = module / f"{famille.name}.tf"
        assert chemin.is_file(), f"fichier manquant : {famille.name}.tf"
        contenu = chemin.read_bytes().decode("utf-8")
        for ressource in famille.resources:
            assert f'resource "{ressource}"' in contenu


def test_une_famille_non_retenue_ne_produit_rien(tmp_path):
    """Le choix vaut aussi a l'interieur d'un domaine."""
    _genere(tmp_path, _base(resources=["namespace"]))
    module = tmp_path / "terraform" / "modules" / "boutique"
    produits = sorted(chemin.name for chemin in module.glob("*.tf"))
    assert produits == ["locals.tf", "namespace.tf", "outputs.tf", "variables.tf", "versions.tf"]


def test_sans_la_famille_namespace_le_module_se_rattache_a_l_existant(tmp_path):
    _genere(tmp_path, _base(resources=["quota"]))
    locals_tf = (tmp_path / "terraform" / "modules" / "boutique" / "locals.tf").read_bytes()
    texte = locals_tf.decode("utf-8")
    assert "namespace = var.namespace" in texte
    assert "kubernetes_namespace.this" not in texte


def test_toute_variable_declaree_est_employee_par_un_gabarit(tmp_path):
    """Verrou contre la regle tflint `terraform_unused_declarations`.

    Elle est verifiee ici sur **chaque famille prise isolement** : le cas
    complet la satisferait meme si une variable n'etait employee que par une
    autre famille.
    """
    for famille in FAMILIES:
        cible = tmp_path / famille.name
        _genere(cible, _base(resources=[famille.name]))
        module = cible / "terraform" / "modules" / "boutique"
        corps = "\n".join(
            chemin.read_bytes().decode("utf-8")
            for chemin in module.glob("*.tf")
            if chemin.name != "variables.tf"
        )
        declarees = {
            ligne.split('"')[1]
            for ligne in (module / "variables.tf").read_bytes().decode("utf-8").splitlines()
            if ligne.startswith('variable "')
        }
        inutilisees = sorted(nom for nom in declarees if f"var.{nom}" not in corps)
        assert inutilisees == [], f"{famille.name} : variables inutilisees {inutilisees}"


#: Ce qu'aucun fichier genere ne doit contenir. Les motifs portent sur des
#: **affectations litterales**, pas sur des mentions : `password = var.x` est
#: licite, `password = "x"` ne l'est pas, et une famille nommee
#: `generated_secret_keys` n'est pas un secret.
MOTIFS_INTERDITS: tuple[tuple[str, str], ...] = (
    (
        r"(?m)^\s*(?:access_key|secret_key|sas_token|client_secret|credentials)\s*=",
        "cle d'acces au stockage d'etat",
    ),
    (
        r'(?m)^\s*\w*(?:password|token|secret)\w*\s*=\s*"',
        "valeur litterale affectee a une cle secrete",
    ),
    (r"BEGIN (?:RSA )?PRIVATE KEY", "cle privee"),
    (r"BEGIN CERTIFICATE", "certificat"),
)


def test_aucun_fichier_genere_ne_porte_de_valeur_secrete(tmp_path):
    """Regle absolue du projet, verifiee sur la sortie et non sur l'intention."""
    import re

    _genere(tmp_path)
    for chemin in sorted((tmp_path / "terraform").rglob("*")):
        if not chemin.is_file():
            continue
        texte = chemin.read_bytes().decode("utf-8")
        for motif, libelle in MOTIFS_INTERDITS:
            trouve = re.search(motif, texte)
            assert trouve is None, (
                f"{chemin.name} porte un(e) {libelle} : {trouve.group(0).strip()!r}"
            )


def _affectations(chemin: Path) -> dict[str, str]:
    """Lit un fichier d'affectations HCL en dict, alignement ignore."""
    valeurs: dict[str, str] = {}
    for ligne in chemin.read_bytes().decode("utf-8").splitlines():
        if ligne.startswith("#") or "=" not in ligne:
            continue
        cle, _, valeur = ligne.partition("=")
        valeurs[cle.strip()] = valeur.strip()
    return valeurs


def test_les_tfvars_portent_les_valeurs_de_leur_environnement(tmp_path):
    _genere(tmp_path)
    racine = tmp_path / "terraform" / "environments"
    prod = _affectations(racine / "prod" / "terraform.tfvars")
    dev = _affectations(racine / "dev" / "terraform.tfvars")
    assert prod["namespace"] == '"boutique-prod"'
    assert prod["kube_context"] == '"plateforme-prod-eu-west-3"'
    assert prod["quota_cpu"] == '"16"'
    assert dev["quota_cpu"] == '"2"'
    # Le contexte non renseigne retombe sur le nom de l'environnement plutot
    # que sur le contexte courant de la machine.
    assert dev["kube_context"] == '"dev"'
    # Les labels de service et ceux de l'environnement sont fusionnes.
    assert "criticality" in prod["labels"] and "criticality" not in dev["labels"]


def test_le_backend_derive_une_cle_par_environnement(tmp_path):
    _genere(tmp_path)
    racine = tmp_path / "terraform" / "environments"
    for nom in ("dev", "staging", "prod"):
        contenu = (racine / nom / "backend.tf").read_bytes().decode("utf-8")
        assert f'key     = "boutique/{nom}/terraform.tfstate"' in contenu


# ---------------------------------------------------------------------------
# Validateurs declares
# ---------------------------------------------------------------------------


def test_les_validateurs_couvrent_chaque_environnement(tmp_path):
    _, spec, _ = _spec()
    liste = validators.commands(spec, tmp_path)
    libelles = [commande.label for commande in liste]
    assert libelles[0] == "terraform fmt"
    assert libelles[-1] == "tflint"
    for nom in ("dev", "staging", "prod"):
        assert f"terraform init ({nom})" in libelles
        assert f"terraform validate ({nom})" in libelles
    assert len(liste) == 2 + 2 * 3


def test_l_initialisation_ne_touche_pas_au_stockage_d_etat(tmp_path):
    """`forge validate` valide du code : il ne joint aucune infrastructure."""
    _, spec, _ = _spec()
    inits = [c for c in validators.commands(spec, tmp_path) if c.label.startswith("terraform init")]
    assert inits
    for commande in inits:
        assert "-backend=false" in commande.argv


def test_le_cache_de_providers_n_est_declare_que_s_il_existe(tmp_path, monkeypatch):
    monkeypatch.setenv(validators.CACHE_ENV_VAR, str(tmp_path / "inexistant"))
    _, spec, _ = _spec()
    assert not any(
        cle == "TF_PLUGIN_CACHE_DIR"
        for commande in validators.commands(spec, tmp_path)
        for cle, _ in commande.env
    )
    monkeypatch.setenv(validators.CACHE_ENV_VAR, str(tmp_path))
    assert any(
        cle == "TF_PLUGIN_CACHE_DIR"
        for commande in validators.commands(spec, tmp_path)
        for cle, _ in commande.env
    )


# ---------------------------------------------------------------------------
# Catalogue et entretien
# ---------------------------------------------------------------------------


def test_le_catalogue_expose_chaque_famille_avec_ses_options():
    from forge.plugins.terraform import plugin as terraform_plugin

    entrees = terraform_plugin.forge_catalog()
    assert [entree.name for entree in entrees] == list(family_names())
    quota = next(entree for entree in entrees if entree.name == "quota")
    assert "quota_cpu" in quota.options
    assert "requests" in quota.details


def test_l_entretien_produit_une_section_valide():
    from forge.plugins.terraform import interview
    from tests.scripted_prompter import ScriptedPrompter

    service = validate_spec(_base(resources=["namespace"]), _manager()).service
    prompter = ScriptedPrompter(
        [
            ["namespace", "quota"],   # familles
            "~> 1.9",                 # contrainte de version
            "per_env",                # strategie de namespace
            "local",                  # backend
            "kubeconfig",             # authentification
            "~/.kube/config",         # chemin du kubeconfig
            True,                     # un contexte par environnement
            True,                     # makefile
            True,                     # .tflint.hcl
        ]
    )
    section = interview.run(prompter, service)
    assert prompter.exhausted, f"reponses non consommees : {prompter.answers}"
    modele = TerraformSpec.model_validate(section)
    assert modele.family_names() == ("namespace", "quota")


def test_l_entretien_decline_quand_aucune_famille_n_est_retenue():
    """Arbitrage R7 : `None` signifie « rien a generer », pas « domaine refuse »."""
    from forge.plugins.terraform import interview
    from tests.scripted_prompter import ScriptedPrompter

    service = validate_spec(_base(resources=["namespace"]), _manager()).service
    assert interview.run(ScriptedPrompter([[]]), service) is None


def test_l_entretien_demande_les_namespaces_en_strategie_custom():
    from forge.plugins.terraform import interview
    from tests.scripted_prompter import ScriptedPrompter

    service = validate_spec(_base(resources=["namespace"]), _manager()).service
    prompter = ScriptedPrompter(
        [
            ["namespace"],
            "~> 1.9",
            "custom",
            "local",
            "kubeconfig",
            "~/.kube/config",
            True,
            "socle-dev",
            "socle-prod",
            False,
            False,
        ]
    )
    section = interview.run(prompter, service)
    assert prompter.exhausted
    assert section["environments"] == {
        "dev": {"namespace": "socle-dev"},
        "prod": {"namespace": "socle-prod"},
    }


# ---------------------------------------------------------------------------
# Validation reelle du projet genere
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_le_projet_genere_passe_ses_propres_validateurs(tmp_path):
    """Regle dure de CLAUDE.md, sur le cas qui active les sept familles.

    C'est le seul juge de ce domaine : il n'existe aucun instantane de parite.
    `terraform init` telecharge des providers au premier passage — la variable
    FORGE_TF_PLUGIN_CACHE evite de recommencer a chaque environnement.
    """
    from forge.validate import tools

    for outil in ("terraform", "tflint"):
        if not tools.probe(outil, True).available:
            pytest.skip(f"{outil} introuvable, nativement comme dans WSL")

    spec, manager = _genere(tmp_path)
    resultat = pipeline.validate(spec, manager, tmp_path)
    echecs = [check for rapport in resultat.reports for check in rapport.failures()]
    assert not echecs, (
        f"validateurs en echec : {', '.join(c.label for c in echecs)}\n"
        + "\n".join(c.detail for c in echecs)[:2000]
    )
    lances = [c.label for rapport in resultat.reports for c in rapport.checks]
    assert "tflint" in lances and "terraform fmt" in lances
