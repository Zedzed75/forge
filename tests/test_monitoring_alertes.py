"""Coherence du catalogue d'alertes, et de chaque alerte avec son test.

Separe de `test_plugin_monitoring.py` pour rester sous la limite de 600 lignes,
et parce que ces controles portent sur autre chose : non pas sur ce que le
domaine produit, mais sur la **tenue interne du catalogue** — qu'aucune alerte
ne cite un seuil que le modele ne declare pas, qu'aucune ne soit livree sans
test, et qu'aucun test ne verifie une formulation que la regle n'emploie plus.

C'est ce dernier point qui compte le plus : `promtool test rules` compare les
annotations caractere par caractere. Un test qui verifierait une ancienne
formulation passerait au vert sans plus rien prouver.
"""

from __future__ import annotations

import re

import pytest

from forge.plugins.monitoring import derive, render
from forge.plugins.monitoring.catalog.families import FAMILIES
from forge.plugins.monitoring.catalog.registry import all_alerts, family_names
from forge.plugins.monitoring.enums import RuleFamily
from forge.plugins.monitoring.spec import ThresholdsSpec, _seconds
from tests.test_plugin_monitoring import _spec


# ---------------------------------------------------------------------------
# Coherence interne du catalogue
# ---------------------------------------------------------------------------


def test_toutes_les_familles_de_l_enumeration_sont_au_catalogue():
    assert set(family_names()) == {famille.value for famille in RuleFamily}


def test_chaque_famille_documente_ses_pieges():
    muettes = [famille.name for famille in FAMILIES if not famille.traps]
    assert muettes == [], f"familles sans piege documente : {muettes}"


def test_chaque_seuil_du_catalogue_existe_dans_le_modele():
    """Un seuil que `ThresholdsSpec` ne declare pas serait inatteignable."""
    champs = set(ThresholdsSpec.model_fields)
    cites = {alerte.threshold_field for alerte in all_alerts() if alerte.threshold_field}
    assert cites <= champs, f"seuils sans champ de modele : {sorted(cites - champs)}"


def test_chaque_seuil_du_modele_est_employe_par_une_alerte():
    """Un champ que personne n'emploie est un reglage sans effet."""
    champs = set(ThresholdsSpec.model_fields)
    cites = {alerte.threshold_field for alerte in all_alerts() if alerte.threshold_field}
    assert champs <= cites, f"seuils inemployes : {sorted(champs - cites)}"


def test_chaque_alerte_porte_un_test_unitaire():
    nues = [alerte.name for alerte in all_alerts() if not alerte.test_series]
    assert nues == [], f"alertes sans serie de test : {nues}"


def test_l_instant_d_evaluation_depasse_la_clause_for():
    """Sinon l'alerte serait encore en attente et le test verifierait le vide."""
    trop_tot = [
        alerte.name
        for alerte in all_alerts()
        if _seconds(alerte.test_eval_time) <= _seconds(alerte.for_duration)
    ]
    assert trop_tot == [], f"instants d'evaluation trop precoces : {trop_tot}"


def test_les_alertes_ont_des_noms_distincts():
    noms = [alerte.name for alerte in all_alerts()]
    assert len(set(noms)) == len(noms)


# ---------------------------------------------------------------------------
# Coherence entre une regle et son test
# ---------------------------------------------------------------------------


def test_l_annotation_attendue_est_celle_de_la_regle_resolue():
    """Elles sont calculees ensemble : elles ne peuvent pas diverger.

    C'est le verrou contre la seule duplication dangereuse du domaine — un test
    qui verifierait une ancienne formulation ne verifierait plus rien.
    """
    _, spec, _ = _spec()
    for env in derive.environments(spec):
        for groupe in env["rules"].values():
            for alerte in groupe["alerts"]:
                attendue = alerte["test"]["exp_annotations"]["description"]
                rendue = render.render_description(
                    alerte["description"], alerte["test"]["exp_labels"]
                )
                assert attendue == rendue, alerte["name"]


def test_aucune_reference_de_libelle_ne_reste_non_resolue():
    """Une reference non resolue signale une alerte qui cite un libelle absent."""
    _, spec, _ = _spec()
    for env in derive.environments(spec):
        for groupe in env["rules"].values():
            for alerte in groupe["alerts"]:
                assert "$labels" not in alerte["test"]["exp_annotations"]["description"], (
                    alerte["name"]
                )


def test_aucun_jeton_du_catalogue_ne_survit_a_la_projection():
    """Un `@jeton@` oublie produit un fichier que promtool refuse — tres loin d'ici."""
    _, spec, _ = _spec()
    reste = re.compile(r"@[a-z_]+@")
    for env in derive.environments(spec):
        for groupe in env["rules"].values():
            for alerte in groupe["alerts"]:
                for cle in ("expr", "summary", "description", "panel_expr"):
                    assert not reste.search(alerte[cle]), f"{alerte['name']} / {cle}"
                for serie in alerte["test"]["series"]:
                    assert not reste.search(serie["series"]), alerte["name"]
                    assert not reste.search(serie["points"]), alerte["name"]


def test_les_series_de_test_suivent_les_seuils():
    """Une serie figee ne prouverait la regle que pour un seul seuil.

    C'est le defaut que `promtool test rules` a trouve : un quantile de test a
    1.9 s validait un seuil a 1 s et echouait sur un seuil a 2 s.
    """
    doux = derive._test_tokens({"cpu_cores": 1.0, "latency_p95_seconds": 1.0})
    serre = derive._test_tokens({"cpu_cores": 4.0, "latency_p95_seconds": 3.0})
    assert serre["cpu_step"] > doux["cpu_step"]
    assert serre["latency_high_le"] > doux["latency_high_le"]


def test_les_seuils_par_defaut_viennent_du_catalogue():
    """Les recopier ailleurs les ferait diverger au premier reglage."""
    defauts = derive.default_thresholds()
    attendus = {
        alerte.threshold_field: alerte.threshold_default
        for alerte in all_alerts()
        if alerte.threshold_field
    }
    assert defauts == attendus


def test_un_nombre_se_rend_pareil_dans_l_expression_et_dans_le_texte():
    """`> 1.0` dans la regle et « depasse 1 seconde » dans le texte suffirait
    a rendre le test unitaire faux."""
    assert render.format_number(1.0) == "1"
    assert render.format_number(0.05) == "0.05"
    assert render.percent(0.05) == "5"
    assert render.percent(0.855) == "85.5"


@pytest.mark.parametrize(
    ("service", "attendu"),
    [("boutique", "Boutique"), ("db-proxy", "DbProxy"), ("mon_service", "MonService")],
)
def test_le_prefixe_d_alerte_est_un_identifiant_camel(service, attendu):
    assert render.alert_prefix(service) == attendu
