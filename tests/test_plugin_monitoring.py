"""Domaine monitoring — le domaine dont les defauts sont silencieux.

Une regle d'alerte peut etre syntaxiquement irreprochable et ne jamais se
declencher : nom de metrique inexistant, libelle mal orthographie, comparaison
du mauvais cote du seuil. Rien n'echoue, rien ne casse, et personne n'est prevenu
le jour ou il aurait fallu l'etre.

D'ou l'organisation de ce module : au-dela des controles habituels, il verifie
la **coherence entre une regle et son test unitaire**, et laisse `promtool test
rules` trancher pour de bon sous le marqueur `integration`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from forge import pipeline
from forge.plugins.monitoring import answers, derive, render, tree, validators
from forge.plugins.monitoring.catalog.families import FAMILIES
from forge.plugins.monitoring.catalog.registry import all_alerts, family_names
from forge.plugins.monitoring.enums import RuleFamily
from forge.plugins.monitoring.spec import MonitoringSpec, ThresholdsSpec
from forge.plugins_api.manager import ForgeManager
from forge.spec.assembly import validate_spec
from forge.spec.io import load_spec_data
from tests.conftest import SPECS_DIR

PLUGIN = "forge.plugins.monitoring.plugin"
SPEC_COMPLETE = SPECS_DIR / "monitoring-complet.yml"


def _manager() -> ForgeManager:
    instance = ForgeManager()
    instance.register_module(PLUGIN)
    return instance


def _spec(donnees: dict | None = None):
    manager = _manager()
    data = donnees if donnees is not None else load_spec_data(SPEC_COMPLETE)
    return data, validate_spec(data, manager), manager


def _base(**monitoring) -> dict:
    """Specification minimale, avec la section monitoring fournie."""
    return {
        "forge_version": 1,
        "service": {
            "name": "boutique",
            "description": "Boutique en ligne",
            "owner": "Equipe",
            "environments": [{"name": "dev"}, {"name": "prod", "production": True}],
        },
        "monitoring": monitoring or {"rules": ["availability"]},
    }


def _genere(tmp_path: Path, donnees: dict | None = None):
    data, spec, manager = _spec(donnees)
    pipeline.generate(data, spec, manager, tmp_path)
    return spec, manager


def _issues(donnees: dict, level: str) -> list[str]:
    spec = validate_spec(donnees, _manager())
    return [issue.message for issue in answers.cross_check(spec) if issue.level == level]


# ---------------------------------------------------------------------------
# Ce que le sous-modele refuse
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("duree", ["30", "5 m", "abc", ""])
def test_une_duree_mal_formee_est_refusee(duree):
    with pytest.raises(ValueError):
        MonitoringSpec(scrape={"interval": duree})


def test_un_delai_superieur_a_l_intervalle_est_refuse():
    """Sinon les collectes se chevauchent, et le collecteur prend du retard."""
    with pytest.raises(ValueError, match="chevaucheraient"):
        MonitoringSpec(scrape={"interval": "10s", "timeout": "30s"})


@pytest.mark.parametrize("nom", ["1metrique", "metrique-tiret", "métrique"])
def test_un_nom_de_metrique_invalide_est_refuse(nom):
    with pytest.raises(ValueError):
        MonitoringSpec(metrics={"requests_total": nom})


@pytest.mark.parametrize("cible", ["api.example.net", "api.example.net:", ":9090", "http://x:1"])
def test_une_cible_mal_formee_est_refusee(cible):
    with pytest.raises(ValueError):
        MonitoringSpec(environments={"dev": {"targets": [cible]}})


def test_une_url_de_sonde_sans_schema_est_refusee():
    with pytest.raises(ValueError):
        MonitoringSpec(environments={"dev": {"probe_urls": ["boutique.example.net"]}})


def test_une_famille_repetee_est_refusee():
    with pytest.raises(ValueError, match="familles de regles"):
        MonitoringSpec(rules=["availability", "availability"])


def test_un_seuil_hors_bornes_est_refuse():
    """Un taux d'erreur de 1 alerterait sur un service parfaitement sain."""
    with pytest.raises(ValueError):
        ThresholdsSpec(error_rate=1.0)


def test_une_cle_inconnue_est_refusee():
    with pytest.raises(ValueError):
        MonitoringSpec(blackbox_adress="x:9115")


# ---------------------------------------------------------------------------
# Ce que le controle croise signale
# ---------------------------------------------------------------------------


def test_un_environnement_inconnu_est_une_erreur():
    donnees = _base(rules=["availability"], environments={"recette": {"targets": ["a:1"]}})
    assert any("recette" in message for message in _issues(donnees, "error"))


def test_un_environnement_sans_cible_est_signale():
    """Le defaut le plus grave du domaine, et le plus silencieux."""
    donnees = _base(rules=["availability"])
    avertissements = _issues(donnees, "warning")
    assert any("aucune cible" in message and "'dev'" in message for message in avertissements)
    assert any("aucune alerte ne pourra se declencher" in message for message in avertissements)


def test_la_famille_probe_sans_url_sondee_est_signalee():
    donnees = _base(
        rules=["probe"],
        environments={"dev": {"targets": ["a:1"]}, "prod": {"targets": ["b:1"]}},
    )
    avertissements = _issues(donnees, "warning")
    assert any("ne se declencheront jamais" in message for message in avertissements)


def test_une_url_sondee_en_clair_est_signalee():
    """`probe_ssl_earliest_cert_expiry` n'existe pas pour une sonde http://."""
    donnees = _base(
        rules=["probe"],
        environments={
            "dev": {"targets": ["a:1"], "probe_urls": ["http://boutique.example.net"]},
            "prod": {"targets": ["b:1"], "probe_urls": ["https://boutique.example.net"]},
        },
    )
    avertissements = _issues(donnees, "warning")
    assert any("probe_ssl_earliest_cert_expiry" in message for message in avertissements)


def test_un_namespace_absent_est_signale_quand_une_famille_en_depend():
    donnees = _base(
        rules=["saturation"],
        environments={"dev": {"targets": ["a:1"]}, "prod": {"targets": ["b:1"]}},
    )
    assert any("namespace" in message for message in _issues(donnees, "warning"))


def test_un_namespace_absent_ne_dit_rien_quand_aucune_famille_n_en_depend():
    donnees = _base(
        rules=["availability"],
        environments={"dev": {"targets": ["a:1"]}, "prod": {"targets": ["b:1"]}},
    )
    assert not any("namespace" in message for message in _issues(donnees, "warning"))


def test_un_seuil_sans_sa_famille_est_signale():
    """Une valeur soigneusement choisie et ignoree en silence est pire qu'une erreur."""
    donnees = _base(
        rules=["availability"],
        environments={
            "dev": {"targets": ["a:1"]},
            "prod": {"targets": ["b:1"], "thresholds": {"error_rate": 0.1}},
        },
    )
    avertissements = _issues(donnees, "warning")
    assert any("thresholds.error_rate" in message for message in avertissements)
    assert any("ne sera pas appliquee" in message for message in avertissements)


def test_la_specification_de_reference_ne_leve_aucune_erreur():
    _, spec, _ = _spec()
    assert [issue for issue in answers.cross_check(spec) if issue.level == "error"] == []


def test_le_controle_croise_est_muet_sans_section_monitoring():
    class Sans:
        pass

    assert answers.cross_check(Sans()) == []


# ---------------------------------------------------------------------------
# Projection
# ---------------------------------------------------------------------------


def test_la_projection_est_serialisable_et_deterministe():
    _, spec, _ = _spec()
    assert json.dumps(answers.build(spec), sort_keys=True) == json.dumps(
        answers.build(spec), sort_keys=True
    )


#: Noms qu'une cle de projection ne peut pas porter : en Jinja, `objet.values`
#: resout la methode du dict avant la cle, et le gabarit ecrit alors
#: `<built-in method values...>` dans le fichier genere. promtool s'en plaint,
#: mais tres loin de la cause. C'est arrive une fois ; ce test l'interdit.
NOMS_RESERVES = frozenset(nom for nom in dir(dict) if not nom.startswith("_"))


def _cles(valeur, chemin=""):
    if isinstance(valeur, dict):
        for cle, sous in valeur.items():
            yield chemin, cle
            yield from _cles(sous, f"{chemin}.{cle}")
    elif isinstance(valeur, list):
        for element in valeur:
            yield from _cles(element, chemin)


def test_aucune_cle_de_projection_ne_masque_une_methode_de_dict():
    _, spec, _ = _spec()
    fautives = [
        f"{chemin}.{cle}" for chemin, cle in _cles(answers.build(spec)) if cle in NOMS_RESERVES
    ]
    assert fautives == [], f"cles masquant une methode de dict : {sorted(set(fautives))}"


def test_les_seuils_different_reellement_d_un_environnement_a_l_autre():
    """Sans cela, une configuration par environnement n'aurait aucun interet."""
    _, spec, _ = _spec()
    environnements = {env["name"]: env for env in derive.environments(spec)}
    assert (
        environnements["dev"]["thresholds"]["error_rate"]
        != environnements["prod"]["thresholds"]["error_rate"]
    )


def test_la_facette_declaree_appartient_au_vocabulaire_partage():
    from forge.plugins.monitoring import plugin as monitoring_plugin
    from forge.validate.consistency import FACET_VOCABULARY

    _, spec, _ = _spec()
    projection = monitoring_plugin.forge_projection(spec)
    assert set(projection.facets) <= set(FACET_VOCABULARY)
    assert projection.facets["ingress_hosts"] == (
        "boutique.dev.example.net",
        "boutique.example.net",
    )


def test_un_environnement_sans_cible_n_est_pas_declare_materialise():
    """Pretendre surveiller ce qu'on ne collecte pas serait pire que se taire."""
    from forge.plugins.monitoring import plugin as monitoring_plugin

    donnees = _base(rules=["availability"], environments={"prod": {"targets": ["a:1"]}})
    spec = validate_spec(donnees, _manager())
    assert monitoring_plugin.forge_projection(spec).environments == ("prod",)


# ---------------------------------------------------------------------------
# Rendu
# ---------------------------------------------------------------------------


def test_l_arborescence_annoncee_correspond_aux_fichiers_generes(tmp_path):
    """Arbitrage R3 : `tree.py` reste au plugin, mais un test le tient a jour."""
    spec, _ = _genere(tmp_path)
    base = tmp_path / "monitoring"
    produits = {
        chemin.relative_to(base).as_posix() for chemin in base.rglob("*") if chemin.is_file()
    }
    assert produits == set(tree.expected_paths(spec))


def test_chaque_famille_retenue_produit_ses_regles_par_environnement(tmp_path):
    spec, _ = _genere(tmp_path)
    base = tmp_path / "monitoring"
    for env in ("dev", "prod"):
        for famille in FAMILIES:
            chemin = base / tree.rule_file(env, famille.name)
            assert chemin.is_file(), chemin
            contenu = chemin.read_bytes().decode("utf-8")
            assert f"boutique-{env}-{famille.name}" in contenu


def test_une_famille_non_retenue_ne_produit_rien(tmp_path):
    """Le choix vaut aussi a l'interieur d'un domaine."""
    donnees = _base(
        rules=["availability"],
        environments={"dev": {"targets": ["a:1"]}, "prod": {"targets": ["b:1"]}},
    )
    _genere(tmp_path, donnees)
    regles = sorted(chemin.name for chemin in (tmp_path / "monitoring" / "rules" / "dev").iterdir())
    assert regles == ["availability.yml"]


def test_les_tests_unitaires_ne_sont_pas_optionnels():
    """Decision de conception : les rendre facultatifs invitait au mauvais choix.

    Une regle d'alerte non testee est une regle dont personne ne sait si elle se
    declenche. `extras` ne porte donc aucun drapeau pour s'en passer.
    """
    from forge.plugins.monitoring.spec import MonitoringExtras

    assert "rule_tests" not in MonitoringExtras.model_fields


def test_chaque_famille_retenue_produit_son_test_unitaire(tmp_path):
    spec, _ = _genere(tmp_path)
    base = tmp_path / "monitoring"
    for env in ("dev", "prod"):
        for famille in FAMILIES:
            assert (base / tree.test_file(env, famille.name)).is_file()


def test_le_tableau_de_bord_est_un_json_valide(tmp_path):
    """Aucun linter Grafana hors ligne n'existe : cette garantie est la notre."""
    _genere(tmp_path)
    chemin = tmp_path / "monitoring" / "grafana" / "dashboards" / "boutique.json"
    tableau = json.loads(chemin.read_bytes().decode("utf-8"))

    assert tableau["title"].startswith("boutique")
    assert tableau["uid"]
    assert tableau["schemaVersion"] >= 36
    panneaux = tableau["panels"]
    assert len(panneaux) == len(list(all_alerts()))
    identifiants = [panneau["id"] for panneau in panneaux]
    assert len(set(identifiants)) == len(identifiants)
    for panneau in panneaux:
        assert panneau["targets"][0]["expr"].strip()
        assert panneau["gridPos"]["w"] > 0


def test_la_configuration_du_collecteur_designe_les_regles_de_son_environnement(tmp_path):
    _genere(tmp_path)
    for env in ("dev", "prod"):
        contenu = (
            (tmp_path / "monitoring" / tree.config_file(env)).read_bytes().decode("utf-8")
        )
        assert f"../../rules/{env}/*.yml" in contenu


def test_la_sonde_blackbox_n_est_configuree_que_si_une_famille_l_exige(tmp_path):
    donnees = _base(
        rules=["availability"],
        environments={"dev": {"targets": ["a:1"]}, "prod": {"targets": ["b:1"]}},
    )
    _genere(tmp_path, donnees)
    contenu = (
        (tmp_path / "monitoring" / tree.config_file("dev")).read_bytes().decode("utf-8")
    )
    assert "blackbox" not in contenu


# ---------------------------------------------------------------------------
# Validateurs declares
# ---------------------------------------------------------------------------


def test_les_validateurs_couvrent_chaque_environnement(tmp_path):
    _, spec, _ = _spec()
    libelles = [commande.label for commande in validators.commands(spec, tmp_path)]
    for env in ("dev", "prod"):
        assert f"promtool check config ({env})" in libelles
        assert f"promtool check rules ({env})" in libelles
        assert f"promtool test rules ({env})" in libelles


def test_les_chemins_de_regles_sont_enumeres_et_non_glisses_en_glob(tmp_path):
    """Les commandes sont lancees sans shell : un `*` ne serait pas developpe."""
    _, spec, _ = _spec()
    for commande in validators.commands(spec, tmp_path):
        assert not any("*" in argument for argument in commande.argv)


def test_le_nombre_de_commandes_suit_les_environnements(tmp_path):
    """Trois commandes par environnement : config, regles, tests."""
    _, spec, _ = _spec()
    assert len(validators.commands(spec, tmp_path)) == 3 * 2


# ---------------------------------------------------------------------------
# Catalogue et entretien
# ---------------------------------------------------------------------------


def test_le_catalogue_expose_chaque_famille_avec_ses_seuils():
    from forge.plugins.monitoring import plugin as monitoring_plugin

    entrees = monitoring_plugin.forge_catalog()
    assert [entree.name for entree in entrees] == list(family_names())
    latence = next(entree for entree in entrees if entree.name == "latency")
    assert "latency_p95_seconds" in latence.options
    assert "histogram_quantile" in latence.details


def test_l_entretien_produit_une_section_valide():
    from forge.plugins.monitoring import interview
    from tests.scripted_prompter import ScriptedPrompter

    service = validate_spec(_base(rules=["availability"]), _manager()).service
    prompter = ScriptedPrompter(
        [
            ["availability", "error_rate"],   # familles
            "http_requests_total",            # compteur de requetes
            "status",                         # libelle de statut
            "api-dev.example.net:9090",       # cibles dev
            "api.example.net:9090",           # cibles prod
            True,                             # tableau de bord
            True,                             # makefile
        ]
    )
    section = interview.run(prompter, service)
    assert prompter.exhausted, f"reponses non consommees : {prompter.answers}"
    modele = MonitoringSpec.model_validate(section)
    assert modele.family_names() == ("availability", "error_rate")
    assert modele.overrides("prod").targets == ["api.example.net:9090"]


def test_l_entretien_decline_quand_aucune_famille_n_est_retenue():
    """Arbitrage R7 : `None` signifie « rien a generer »."""
    from forge.plugins.monitoring import interview
    from tests.scripted_prompter import ScriptedPrompter

    service = validate_spec(_base(rules=["availability"]), _manager()).service
    assert interview.run(ScriptedPrompter([[]]), service) is None


# ---------------------------------------------------------------------------
# Validation reelle du projet genere
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_le_projet_genere_passe_ses_propres_validateurs(tmp_path):
    """Regle dure de CLAUDE.md, sur le cas qui active les six familles.

    `promtool test rules` est le seul validateur du projet qui verifie quelque
    chose de **semantique** : que les alertes se declenchent reellement.
    """
    from tests.conftest import require_tools

    require_tools("monitoring", "promtool")

    spec, manager = _genere(tmp_path)
    resultat = pipeline.validate(spec, manager, tmp_path)
    echecs = [check for rapport in resultat.reports for check in rapport.failures()]
    assert not echecs, (
        f"validateurs en echec : {', '.join(c.label for c in echecs)}\n"
        + "\n".join(c.detail for c in echecs)[:2000]
    )
    lances = [c.label for rapport in resultat.reports for c in rapport.checks]
    assert any("test rules" in libelle for libelle in lances)
