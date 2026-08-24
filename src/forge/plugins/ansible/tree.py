"""Arborescence ASCII du projet genere — **seul vestige du planner legacy**.

Le README du projet genere affiche l'arborescence complete de ce projet. copier
ne peut pas la fournir : au moment ou il rend un fichier, il ne sait pas encore
quels autres fichiers il ecrira. Il faut donc reconstruire la liste des chemins
sans rien rendre.

:func:`expected_paths` est la reduction de `ansible_forge.engine.planner.plan`
a ses seuls chemins : meme decoupage en sections, memes conditions, mais aucun
contenu. C'est le **seul** endroit de forge qui duplique la connaissance de
l'arborescence de gabarit : si un gabarit est ajoute, retire ou renomme, il faut
le repercuter ici, sinon le README ment. Le test de parite le detecte, parce
qu'il compare `README.md` octet pour octet.

:func:`build_tree` est le portage litteral de `ansible_forge.engine.writer.build_tree`
— memes caracteres de branche, meme tri (repertoires d'abord, puis fichiers,
chacun par ordre alphabetique), meme dedoublonnage.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

#: Caracteres de dessin de l'arborescence (portage de `writer`).
_BRANCH = "├── "
_LAST_BRANCH = "└── "
_VERTICAL = "│   "
_SPACE = "    "

#: Fichiers ecrits pour **tous** les roles, sous `roles/<role>/`.
SHARED_ROLE_FILES: tuple[str, ...] = (
    "defaults/main.yml",
    "meta/main.yml",
    "README.md",
)

#: Fichiers propres a chaque role, sous `roles/<role>/`.
#: Portage des destinations de `role_planner.ROLE_FILES` (les sources de gabarit
#: ne servent plus a rien : copier les trouve tout seul dans `template/roles/`).
ROLE_FILES: dict[str, tuple[str, ...]] = {
    "common": (
        "tasks/main.yml",
        "handlers/main.yml",
        "vars/main.yml",
        "templates/motd.j2",
    ),
    "users": (
        "tasks/main.yml",
        "vars/main.yml",
        "templates/sudoers.j2",
    ),
    "ssh_hardening": (
        "tasks/main.yml",
        "handlers/main.yml",
        "vars/main.yml",
        "templates/hardening.conf.j2",
    ),
    "firewall": (
        "tasks/main.yml",
        "tasks/ufw.yml",
        "tasks/firewalld.yml",
        "handlers/main.yml",
        "vars/main.yml",
    ),
    "nginx": (
        "tasks/main.yml",
        "handlers/main.yml",
        "vars/main.yml",
        "templates/nginx.conf.j2",
        "templates/vhost.conf.j2",
    ),
    "docker": (
        "tasks/main.yml",
        "tasks/repository_debian.yml",
        "tasks/repository_redhat.yml",
        "handlers/main.yml",
        "vars/main.yml",
        "templates/daemon.json.j2",
    ),
    "postgresql": (
        "tasks/main.yml",
        "handlers/main.yml",
        "vars/main.yml",
    ),
}

#: Chemins affiches dans l'arborescence sans etre ecrits par forge.
#:
#: Le planner legacy ecrivait une copie de la specification dans le projet
#: (option `embed_spec`). forge ne le fait plus : la specification unifiee vit a
#: la racine du depot cible, au-dessus de `ansible/` (MIGRATION.md §7, ecart 3).
#: L'entree est conservee dans l'arborescence pour que `README.md` reste
#: identique a l'instantane de parite ; c'est un choix assume, a lever en meme
#: temps que les autres mentions legacy du README (`ansible-forge generate`).
LEGACY_TREE_ENTRIES: tuple[str, ...] = ("forge.yml",)

#: Fichiers ecrits par copier mais volontairement absents de l'arborescence :
#: `.copier-answers.yml` est de la plomberie de generation, pas du projet
#: Ansible (MIGRATION.md §7, ecart 1).
HIDDEN_ENTRIES: tuple[str, ...] = (".copier-answers.yml",)


def expected_paths(spec: Any) -> list[str]:
    """Chemins que forge va ecrire, tries — reduction du planner a ses chemins.

    Suit section par section l'ordre de `planner.plan` : fichiers de projet,
    variables de racine, inventaires, playbooks, roles, README.
    """
    ansible = spec.ansible
    options = ansible.options
    chemins: list[str] = ["ansible.cfg", "requirements.yml"]

    if options.write_lint_config:
        chemins += [".gitignore", ".yamllint", ".ansible-lint"]
    if options.write_ci:
        chemins.append(".github/workflows/ansible-lint.yml")
    chemins.extend(LEGACY_TREE_ENTRIES)

    chemins.append("group_vars/all.yml")
    chemins += [f"group_vars/{groupe.name}.yml" for groupe in ansible.groups]

    for env in spec.service.environments:
        base = f"inventories/{env.name}"
        chemins.append(f"{base}/hosts.yml")
        chemins.append(f"{base}/group_vars/all/main.yml")
        if options.use_vault:
            chemins.append(f"{base}/group_vars/all/vault.yml.example")
        chemins += [f"{base}/group_vars/{groupe.name}.yml" for groupe in ansible.groups]
        par_groupe = ansible.hosts.get(env.name, {})
        noms = sorted(hote.name for hotes in par_groupe.values() for hote in hotes)
        chemins += [f"{base}/host_vars/{nom}.yml" for nom in noms]

    chemins += ["playbooks/site.yml", "playbooks/ping.yml"]
    chemins += [f"playbooks/{groupe.name}.yml" for groupe in ansible.groups]

    for nom_role in ansible.ordered_used_roles():
        chemins += [f"roles/{nom_role}/{fichier}" for fichier in SHARED_ROLE_FILES]
        chemins += [f"roles/{nom_role}/{fichier}" for fichier in ROLE_FILES[nom_role]]

    chemins.append("README.md")
    return sorted(chemins)


def build_tree(paths: list[str], root: str) -> str:
    """Rend une arborescence lisible a partir d'une liste de chemins relatifs.

    Portage litteral de `writer.build_tree` : `sorted(set(...))` en entree, puis
    rendu recursif.
    """
    arbre = _nest(sorted(set(paths)))
    lignes = [f"{root}/"]
    lignes.extend(_render(arbre, prefix=""))
    return "\n".join(lignes)


def _nest(paths: list[str]) -> dict[str, dict]:
    """Transforme une liste de chemins plats en dictionnaire imbrique."""
    racine: dict[str, dict] = {}
    for chemin in paths:
        noeud = racine
        for part in PurePosixPath(chemin).parts:
            noeud = noeud.setdefault(part, {})
    return racine


def _render(node: dict[str, dict], prefix: str) -> list[str]:
    """Rend recursivement un niveau de l'arborescence.

    Les repertoires (noeuds ayant des enfants) sont listes avant les fichiers,
    puis tries par nom : l'affichage est stable d'une execution a l'autre.
    """
    entrees = sorted(node.items(), key=lambda item: (not item[1], item[0]))
    lignes: list[str] = []
    for index, (nom, enfants) in enumerate(entrees):
        dernier = index == len(entrees) - 1
        connecteur = _LAST_BRANCH if dernier else _BRANCH
        suffixe = "/" if enfants else ""
        lignes.append(f"{prefix}{connecteur}{nom}{suffixe}")
        if enfants:
            lignes.extend(_render(enfants, prefix + (_SPACE if dernier else _VERTICAL)))
    return lignes
