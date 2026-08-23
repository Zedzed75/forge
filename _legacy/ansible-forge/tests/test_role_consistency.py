"""Cohérence entre les métadonnées du catalogue et le code réellement généré.

Ces tests comparent ce que le catalogue *déclare* (collections requises, noms
de handlers) à ce que les templates *produisent*. Sans eux, un rôle peut passer
ansible-lint tout en générant un ``requirements.yml`` faux : le lint local
fonctionne parce que la collection est déjà installée, mais le projet livré
échoue chez l'utilisateur.
"""

from __future__ import annotations

import re

import pytest
import yaml

from ansible_forge.catalog.registry import get_role
from ansible_forge.engine.role_planner import implemented_roles, plan_role
from ansible_forge.models.enums import OSFamily

#: Détecte un appel de module qualifié : « namespace.collection.module: ».
MODULE_RE = re.compile(r"^\s{2,}([a-z_]+\.[a-z_]+)\.[a-z_]+:", re.MULTILINE)

#: Collection intégrée à ansible-core : jamais à déclarer dans requirements.yml.
BUILTIN = "ansible.builtin"


def role_artifacts(name: str, os_family: OSFamily = OSFamily.DEBIAN):
    """Génère un rôle et retourne ses artefacts."""
    return plan_role(name, author="Tests", os_family=os_family, example_group="webservers")


def collections_used(name: str) -> set[str]:
    """Retourne les collections externes réellement appelées par les tâches du rôle."""
    used: set[str] = set()
    for artifact in role_artifacts(name):
        if "/tasks/" in artifact.posix_path or "/handlers/" in artifact.posix_path:
            used.update(MODULE_RE.findall(artifact.content))
    used.discard(BUILTIN)
    return used


@pytest.mark.parametrize("name", implemented_roles())
def test_toutes_les_collections_utilisees_sont_declarees(name: str):
    """Un module community.* non déclaré rendrait requirements.yml incomplet."""
    declared = set(get_role(name).collections)
    missing = sorted(collections_used(name) - declared)
    assert not missing, (
        f"Le rôle « {name} » utilise {missing} sans les déclarer dans son catalogue : "
        "requirements.yml serait incomplet."
    )


@pytest.mark.parametrize("name", implemented_roles())
def test_aucune_collection_declaree_inutile(name: str):
    """Une collection déclarée mais jamais utilisée alourdit l'installation."""
    declared = set(get_role(name).collections)
    unused = sorted(declared - collections_used(name))
    assert not unused, (
        f"Le rôle « {name} » déclare {unused} sans les utiliser : "
        "à retirer du catalogue ou à employer dans les tâches."
    )


@pytest.mark.parametrize("name", implemented_roles())
def test_les_handlers_declares_existent(name: str):
    """Le README du rôle liste les handlers : ils doivent exister réellement."""
    declared = list(get_role(name).handlers)
    handlers = [
        artifact
        for artifact in role_artifacts(name)
        if artifact.posix_path.endswith("handlers/main.yml")
    ]
    if not declared:
        assert not handlers, f"Le rôle « {name} » génère des handlers non déclarés au catalogue."
        return

    assert handlers, f"Le rôle « {name} » déclare des handlers mais n'en génère aucun."
    generated = [task["name"] for task in yaml.safe_load(handlers[0].content)]
    assert sorted(generated) == sorted(declared), (
        f"Handlers du rôle « {name} » : le catalogue annonce {sorted(declared)} "
        f"mais le rôle génère {sorted(generated)}."
    )


@pytest.mark.parametrize("name", implemented_roles())
def test_les_notify_pointent_vers_un_handler_existant(name: str):
    """Un notify vers un handler inexistant est silencieusement ignoré par Ansible."""
    artifacts = role_artifacts(name)
    handler_files = [a for a in artifacts if a.posix_path.endswith("handlers/main.yml")]
    known = {task["name"] for a in handler_files for task in yaml.safe_load(a.content)}

    for artifact in artifacts:
        if "/tasks/" not in artifact.posix_path:
            continue
        for task in yaml.safe_load(artifact.content) or []:
            notified = task.get("notify")
            if notified is None:
                continue
            for handler in [notified] if isinstance(notified, str) else notified:
                assert handler in known, (
                    f"{artifact.posix_path} notifie « {handler} », "
                    f"absent des handlers du rôle « {name} » ({sorted(known)})."
                )


@pytest.mark.parametrize("name", implemented_roles())
def test_toutes_les_taches_sont_nommees(name: str):
    """CLAUDE.md impose un name: explicite sur chaque tâche."""
    for artifact in role_artifacts(name):
        if "/tasks/" not in artifact.posix_path and "/handlers/" not in artifact.posix_path:
            continue
        for index, task in enumerate(yaml.safe_load(artifact.content) or []):
            assert task.get("name"), f"{artifact.posix_path} : tâche n°{index + 1} sans name."


@pytest.mark.parametrize("name", implemented_roles())
def test_aucun_module_court(name: str):
    """CLAUDE.md impose des noms de modules pleinement qualifiés."""
    short = {"package", "file", "template", "service", "user", "group", "command", "copy", "apt"}
    for artifact in role_artifacts(name):
        if "/tasks/" not in artifact.posix_path and "/handlers/" not in artifact.posix_path:
            continue
        for task in yaml.safe_load(artifact.content) or []:
            used = short.intersection(task)
            assert not used, f"{artifact.posix_path} utilise un module court : {sorted(used)}."


@pytest.mark.parametrize("name", implemented_roles())
def test_les_variables_du_role_sont_prefixees(name: str):
    """ansible-lint exige que les variables d'un rôle portent son nom en préfixe."""
    for artifact in role_artifacts(name):
        if not artifact.posix_path.endswith(("defaults/main.yml", "vars/main.yml")):
            continue
        for variable in yaml.safe_load(artifact.content) or {}:
            assert variable.startswith(f"{name}_"), (
                f"{artifact.posix_path} : la variable « {variable} » "
                f"devrait commencer par « {name}_ »."
            )


@pytest.mark.parametrize("name", implemented_roles())
def test_chaque_variable_est_commentee(name: str):
    """CLAUDE.md impose un commentaire décrivant chaque variable et ses valeurs admises."""
    for artifact in role_artifacts(name):
        if not artifact.posix_path.endswith(("defaults/main.yml", "vars/main.yml")):
            continue
        lines = artifact.content.splitlines()
        for index, line in enumerate(lines):
            if not re.match(r"^[a-z_]+:", line):
                continue
            above = [lines[position] for position in range(max(index - 3, 0), index)]
            assert any("Valeurs admises" in text for text in above), (
                f"{artifact.posix_path}:{index + 1} — la variable « {line.split(':')[0]} » "
                "n'est pas précédée de la documentation de ses valeurs admises."
            )
