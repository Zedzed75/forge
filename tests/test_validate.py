"""Tests du runner de validation et des controles inter-domaines."""

from __future__ import annotations

import sys
from pathlib import Path

from forge.plugins_api.types import Command, Projection
from forge.validate import tools
from forge.validate.consistency import compare_projections, format_issues, has_errors
from forge.validate.runner import run_command, run_commands

#: Interpreteur courant : outil externe garanti present, sans dependance reseau.
PYTHON = sys.executable


def _python(label: str, code: str, **kwargs) -> Command:
    return Command(label=label, tool=PYTHON, argv=("-c", code), **kwargs)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def test_une_commande_qui_reussit_est_marquee_ok(tmp_path):
    check = run_command(_python("ok", "print('bien')"), tmp_path)
    assert check.status == "ok"
    assert check.returncode == 0
    assert "bien" in check.stdout


def test_une_commande_en_echec_remonte_sa_sortie(tmp_path):
    check = run_command(
        _python("ko", "import sys; sys.stderr.write('casse'); sys.exit(3)"), tmp_path
    )
    assert check.status == "failed"
    assert check.returncode == 3
    assert "casse" in check.detail


def test_un_outil_absent_donne_un_message_d_installation(tmp_path):
    command = Command(
        label="absent",
        tool="outil-qui-n-existe-pas",
        install_hint="installez-le depuis le depot interne",
    )
    check = run_command(command, tmp_path)
    assert check.status == "missing"
    assert "installez-le depuis le depot interne" in check.detail
    assert "Traceback" not in check.detail


def test_un_depassement_de_delai_est_signale_sans_trace(tmp_path):
    check = run_command(_python("lent", "import time; time.sleep(5)", timeout=1), tmp_path)
    assert check.status == "timeout"
    assert "delai" in check.detail


def test_skip_missing_transforme_l_absence_en_saut(tmp_path):
    command = Command(label="absent", tool="outil-qui-n-existe-pas")
    report = run_commands("demo", [command], tmp_path, skip_missing=True)
    assert report.checks[0].status == "skipped"
    assert report.ok


def test_sans_skip_missing_l_absence_fait_echouer(tmp_path):
    command = Command(label="absent", tool="outil-qui-n-existe-pas")
    report = run_commands("demo", [command], tmp_path)
    assert not report.ok
    assert [check.label for check in report.failures()] == ["absent"]


def test_le_stdin_est_chaine_depuis_la_commande_source(tmp_path):
    commands = [
        _python("produit", "print('charge utile')"),
        _python(
            "consomme",
            "import sys; data = sys.stdin.read(); sys.exit(0 if 'charge utile' in data else 1)",
            stdin_from="produit",
        ),
    ]
    report = run_commands("demo", commands, tmp_path)
    assert [check.status for check in report.checks] == ["ok", "ok"]


def test_un_chainage_sans_source_est_saute_proprement(tmp_path):
    commands = [_python("consomme", "pass", stdin_from="jamais lancee")]
    report = run_commands("demo", commands, tmp_path)
    assert report.checks[0].status == "skipped"
    assert "jamais lancee" in report.checks[0].detail


def test_le_rapport_resume_les_etats(tmp_path):
    report = run_commands(
        "demo",
        [_python("ok", "pass"), Command(label="absent", tool="outil-qui-n-existe-pas")],
        tmp_path,
    )
    assert report.summary().startswith("demo :")
    assert "1 ok" in report.summary()
    assert "1 missing" in report.summary()


def test_la_commande_s_execute_dans_le_repertoire_du_domaine(tmp_path):
    cible = tmp_path / "demo"
    cible.mkdir()
    (cible / "marqueur.txt").write_text("x", encoding="utf-8")
    check = run_command(
        _python("cwd", "import pathlib, sys; sys.exit(0 if pathlib.Path('marqueur.txt').exists() else 1)"),
        cible,
    )
    assert check.status == "ok"


def test_probe_trouve_un_outil_du_path():
    status = tools.probe(PYTHON)
    assert status.available
    assert "disponible" in status.describe()


def test_probe_signale_un_outil_absent():
    status = tools.probe("outil-qui-n-existe-pas")
    assert not status.available
    assert status.describe().endswith("absent")


# ---------------------------------------------------------------------------
# Coherence inter-domaines
# ---------------------------------------------------------------------------


def _projection(**kwargs) -> Projection:
    base = {
        "service_name": "boutique",
        "environments": ("dev", "prod"),
        "labels": {"tier": "frontend"},
        "facets": {},
    }
    base.update(kwargs)
    return Projection(**base)


def test_un_seul_domaine_ne_declenche_aucun_controle():
    assert compare_projections({"demo": _projection()}) == []


def test_deux_domaines_alignes_ne_produisent_aucun_constat():
    issues = compare_projections({"a": _projection(), "b": _projection()})
    assert issues == []
    assert "aucun ecart" in format_issues(issues)


def test_un_nom_de_service_divergent_est_une_erreur():
    issues = compare_projections(
        {"a": _projection(), "b": _projection(service_name="autre")}
    )
    assert has_errors(issues)
    assert "nom de service" in issues[0].message


def test_des_environnements_divergents_sont_une_erreur():
    issues = compare_projections(
        {"a": _projection(), "b": _projection(environments=("dev",))}
    )
    assert has_errors(issues)
    assert "prod" in issues[0].message


def test_un_ordre_d_environnement_different_est_un_avertissement():
    issues = compare_projections(
        {"a": _projection(), "b": _projection(environments=("prod", "dev"))}
    )
    assert not has_errors(issues)
    assert issues[0].level == "warning"


def test_un_label_contradictoire_est_une_erreur():
    issues = compare_projections(
        {"a": _projection(), "b": _projection(labels={"tier": "backend"})}
    )
    assert has_errors(issues)
    assert "tier" in issues[0].message


def test_une_facette_declaree_par_un_seul_domaine_n_est_pas_comparee():
    issues = compare_projections(
        {"a": _projection(facets={"hosts": ("web-01",)}), "b": _projection()}
    )
    assert issues == []


def test_une_facette_declaree_par_deux_domaines_doit_concorder():
    issues = compare_projections(
        {
            "a": _projection(facets={"hosts": ("web-01", "web-02")}),
            "b": _projection(facets={"hosts": ("web-01",)}),
        }
    )
    assert has_errors(issues)
    assert "web-02" in issues[0].message


def test_le_format_des_constats_place_les_erreurs_avant_les_avertissements():
    issues = compare_projections(
        {
            "a": _projection(),
            "b": _projection(environments=("prod", "dev"), labels={"tier": "backend"}),
        }
    )
    rendu = format_issues(issues)
    assert rendu.index("ERREUR") < rendu.index("AVERTIR")


def test_aucune_projection_ne_produit_aucun_constat():
    assert compare_projections({}) == []
