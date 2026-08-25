"""Tests du runner de validation et des controles inter-domaines."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from forge.errors import ForgeError, PluginError
from forge.plugins_api.types import Command, Projection
from forge.validate import tools, wsl
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


def test_un_chainage_vers_un_libelle_inexistant_est_une_erreur_de_plugin(tmp_path):
    """Rupture de contrat cote plugin : la signaler comme un saut ferait passer
    `forge validate` au vert sans avoir lance la commande."""
    commands = [_python("consomme", "pass", stdin_from="jamais declaree")]
    with pytest.raises(PluginError, match="jamais declaree"):
        run_commands("demo", commands, tmp_path)


def test_un_chainage_dont_la_source_a_echoue_est_saute_proprement(tmp_path):
    commands = [
        _python("produit", "import sys; sys.exit(1)"),
        _python("consomme", "pass", stdin_from="produit"),
    ]
    report = run_commands("demo", commands, tmp_path)
    assert [check.status for check in report.checks] == ["failed", "skipped"]
    assert "produit" in report.checks[1].detail


def test_l_extrait_de_sortie_conserve_la_tete_ou_l_erreur_est_annoncee(tmp_path):
    """Les outils d'infra annoncent la cause en premiere ligne, pas en derniere."""
    code = (
        "import sys\n"
        "sys.stderr.write('Error: values.yaml:3 unknown key\\n')\n"
        "sys.stderr.write(''.join(f'contexte {i}\\n' for i in range(200)))\n"
        "sys.exit(1)\n"
    )
    check = run_command(_python("verbeux", code), tmp_path)
    assert check.status == "failed"
    assert "Error: values.yaml:3 unknown key" in check.detail
    assert "ligne(s) omise(s)" in check.detail
    assert not check.detail.splitlines()[0].startswith("  [...")


def test_un_rapport_entierement_saute_est_signale(tmp_path):
    """Un rapport vert ou rien n'a tourne est un piege : il doit se voir."""
    commands = [Command(label="absent", tool="outil-qui-n-existe-pas")]
    report = run_commands("demo", commands, tmp_path, skip_missing=True)
    assert report.all_skipped
    assert [check.label for check in report.skipped()] == ["absent"]


def test_un_rapport_partiellement_execute_n_est_pas_signale(tmp_path):
    commands = [
        _python("ok", "pass"),
        Command(label="absent", tool="outil-qui-n-existe-pas"),
    ]
    report = run_commands("demo", commands, tmp_path, skip_missing=True)
    assert not report.all_skipped


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


def test_un_environnement_materialise_par_un_seul_domaine_est_signale():
    """C'est le constat que seule la comparaison de projections peut produire.

    Un avertissement, pas une erreur : deployer en production sans machine de
    configuration peut etre parfaitement voulu (un service uniquement
    conteneurise). Ce qui ne doit pas arriver, c'est que personne ne le dise.
    """
    issues = compare_projections(
        {"a": _projection(), "b": _projection(environments=("dev",))}
    )
    assert not has_errors(issues)
    assert [issue.level for issue in issues] == ["warning"]
    assert "prod" in issues[0].message
    assert "materialise par a" in issues[0].message
    assert issues[0].hint


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


def test_une_facette_du_vocabulaire_partage_doit_concorder():
    issues = compare_projections(
        {
            "a": _projection(facets={"inventory_hosts": ("web-01", "web-02")}),
            "b": _projection(facets={"inventory_hosts": ("web-01",)}),
        }
    )
    assert has_errors(issues)
    assert "web-02" in issues[0].message


def test_une_facette_hors_vocabulaire_n_est_pas_comparee():
    """Le nom d'une facette est un espace de noms **partage** entre domaines.

    Deux domaines qui emploient le meme nom affirment parler de la meme chose.
    Sans cette regle, la collision est silencieuse : mesure en phase 5, Ansible
    declarait `hosts` pour ses machines et Helm pour ses hotes d'Ingress, et
    `forge validate` echouait sur une specification parfaitement coherente.
    """
    issues = compare_projections(
        {
            "a": _projection(facets={"maison": ("x",)}),
            "b": _projection(facets={"maison": ("y",)}),
        }
    )
    assert issues == []


def test_le_vocabulaire_distingue_les_deux_sortes_d_hotes():
    """Machines d'inventaire et hotes d'Ingress ne sont pas la meme chose."""
    from forge.validate.consistency import FACET_VOCABULARY

    assert "inventory_hosts" in FACET_VOCABULARY
    assert "ingress_hosts" in FACET_VOCABULARY
    assert "hosts" not in FACET_VOCABULARY, (
        "un nom aussi vague invite precisement a la collision qu'on vient de corriger"
    )


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


# ---------------------------------------------------------------------------
# Pont WSL — fonctions pures, verifiables sans distribution installee
# ---------------------------------------------------------------------------


def test_quote_protege_une_apostrophe():
    #  il l'a dit  ->  'il l'\''a dit'  (fermeture, apostrophe echappee, reouverture)
    attendu = "'il l'" + chr(92) + "''a dit'"
    assert wsl.quote("il l'a dit") == attendu


def test_to_wsl_path_traduit_une_lettre_de_lecteur():
    assert wsl.to_wsl_path(Path("C:/projets/demo")) == "/mnt/c/projets/demo"


def test_to_wsl_path_refuse_un_chemin_unc():
    """Fabriquer un chemin plausible mais faux ferait echouer la copie plus loin."""
    with pytest.raises(ForgeError, match="UNC"):
        wsl.to_wsl_path(Path("//nas/share/projet"))


def test_build_command_nettoie_le_repertoire_temporaire_par_un_trap():
    """Sans trap, un depassement de delai laisse une copie du projet dans /tmp."""
    command = wsl.build_command("helm", ("lint",), Path("C:/projets/demo"), None)
    assert "trap 'rm -rf \"$work\"' EXIT HUP INT TERM" in command
    assert command.count("mktemp") == 1


def test_build_command_protege_les_arguments():
    command = wsl.build_command("helm", ("template", "a b"), Path("C:/p"), None)
    assert "'a b'" in command


def test_build_command_transmet_les_variables_d_environnement():
    command = wsl.build_command("ansible-lint", (), Path("C:/p"), {"ANSIBLE_FORCE_COLOR": "0"})
    assert "ANSIBLE_FORCE_COLOR='0'" in command


def test_install_hint_mentionne_la_distribution_sous_windows(monkeypatch):
    monkeypatch.setattr(wsl, "is_windows", lambda: True)
    assert wsl.WSL_DISTRO in wsl.install_hint("helm")
