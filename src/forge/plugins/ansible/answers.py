"""Projection de la specification unifiee vers le dict `domain` de copier.

C'est l'implementation du hook `forge_answers` (DESIGN.md §2.2) pour le domaine
Ansible, et la piece centrale du portage : tous les gabarits lisent ce que ce
module produit.

Contrat, tenu par :func:`build` :

* **memes noms que dans le planner legacy** — convertir un gabarit se reduit a
  changer les delimiteurs et a prefixer `domain.` (ou a utiliser la variable de
  boucle d'un `yield`) ;
* **JSON-serialisable** — aucun objet pydantic, aucun `Enum`, aucun `set` : le
  dict est ecrit tel quel dans `.copier-answers.yml` et rejoue par
  `copier update` ;
* **ordre fige** — cles inserees dans un ordre stable, listes triees de facon
  explicite, jamais par hasard.

Le calcul lui-meme vit dans :mod:`forge.plugins.ansible.derive` (valeurs
derivees) et :mod:`forge.plugins.ansible.tree` (arborescence du README) ; ce
module ne fait que l'assembler.
"""

from __future__ import annotations

from typing import Any

from forge.plugins.ansible import derive, tree
from forge.plugins_api.types import Issue


def build(spec: Any) -> dict[str, Any]:
    """Construit le dict `domain` passe a copier pour le domaine Ansible.

    `spec` est le modele racine assemble : `spec.service` (bloc partage) et
    `spec.ansible` (instance d'`AnsibleSpec`).
    """
    service = spec.service
    ansible = spec.ansible

    # Auteur des roles generes : le responsable du service, a defaut son nom.
    # Portage de `planner._roles` (`spec.author or spec.project_name`).
    author = service.owner or service.name

    contextes = derive.role_contexts(ansible, author=author)
    environments = derive.environments(spec, contextes)

    return {
        # -- identite et parametres de connexion ---------------------------
        "author": author,
        "default_env": service.environments[0].name,
        "env_names": [env.name for env in service.environments],
        "os_family": ansible.os_family.value,
        "remote_user": ansible.remote_user,
        "become": ansible.become,
        "ssh_port": ansible.ssh_port,
        "python_interpreter": ansible.python_interpreter,
        "options": {
            "use_vault": ansible.options.use_vault,
            "write_lint_config": ansible.options.write_lint_config,
            "write_ci": ansible.options.write_ci,
        },
        # -- dependances Galaxy --------------------------------------------
        "collections": derive.collections(ansible),
        "collection_users": derive.collection_users(ansible),
        # -- roles ----------------------------------------------------------
        "roles": contextes,
        "role_slots": derive.role_slots(contextes),
        "role_overrides": derive.role_overrides(ansible),
        # -- groupes et environnements --------------------------------------
        "groups": derive.project_groups(ansible, contextes),
        "environments": environments,
        # -- documentation ---------------------------------------------------
        "tree": tree.build_tree(tree.expected_paths(spec), service.name),
    }


def cross_check(spec: Any) -> list[Issue]:
    """Verifie que `ansible.hosts` et `ansible.group_vars` citent des environnements connus.

    `AnsibleSpec` ne voit que sa propre section : elle peut verifier que les
    groupes cites existent, jamais que les environnements existent, puisque
    ceux-ci sont declares dans le bloc partage `service:`. Ce controle croise
    comble ce trou (cf. `plugin.forge_consistency`).

    Retourne un `Issue` de niveau `error` par environnement inconnu, dans
    l'ordre alphabetique — la liste est affichee telle quelle a l'utilisateur.
    """
    ansible = getattr(spec, "ansible", None)
    if ansible is None:
        return []

    connus = {env.name for env in spec.service.environments}
    declares = ", ".join(env.name for env in spec.service.environments)

    # Un environnement peut etre cite par les deux sections : on ne signale
    # qu'une fois, en nommant les sections fautives.
    sections: dict[str, list[str]] = {}
    for section, table in (("hosts", ansible.hosts), ("group_vars", ansible.group_vars)):
        for nom in table:
            if nom not in connus:
                sections.setdefault(nom, []).append(section)

    issues: list[Issue] = []
    for nom in sorted(sections):
        citantes = [f"ansible.{section}" for section in sections[nom]]
        sujet = " et ".join(citantes)
        verbe = "citent" if len(citantes) > 1 else "cite"
        issues.append(
            Issue(
                level="error",
                message=(
                    f"{sujet} {verbe} l'environnement '{nom}', absent de "
                    f"service.environments (declares : {declares})."
                ),
                hint=(
                    f"Ajoutez un environnement '{nom}' a service.environments, ou "
                    f"corrigez la cle '{nom}' dans {sujet}."
                ),
                domains=("ansible",),
            )
        )
    return issues
