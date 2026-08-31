"""Commandes de validation du projet de supervision genere.

Trois verifications, et la troisieme est celle qui compte vraiment :

1. `promtool check config` — la configuration du collecteur tient debout, et les
   fichiers de regles qu'elle designe existent et sont valides. Une par
   environnement : chaque environnement a sa propre configuration.
2. `promtool check rules` — les regles se relisent : PromQL valide, champs
   obligatoires presents, annotations qui se rendent.
3. `promtool test rules` — **les alertes se declenchent reellement**. On donne
   une serie temporelle synthetique, on evalue a un instant donne, et on verifie
   que l'alerte apparait avec les bons libelles et les bonnes annotations.

La troisieme est la seule qui verifie quelque chose de semantique. Une regle
peut etre syntaxiquement irreprochable et ne jamais se declencher — un nom de
metrique qui n'existe pas, un libelle mal orthographie, un seuil du mauvais cote
de la comparaison. Ni `check config` ni `check rules` ne le voient ; c'est
precisement le defaut que ce domaine peut produire, et il est silencieux.

Aucune de ces commandes ne joint un collecteur : `forge validate` verifie des
fichiers, jamais une infrastructure en fonctionnement.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forge.plugins.monitoring import tree
from forge.plugins_api.types import Command

#: Delai maximal accorde a une commande, en secondes.
TIMEOUT = 120

#: Message d'installation.
INSTALL_HINT = (
    "installez promtool, livre avec Prometheus "
    "(https://prometheus.io/download/). Sous Windows, le pont WSL le cherche "
    "dans /opt/forge-tools/bin ; un lien symbolique suffit."
)

#: Variables d'environnement communes. promtool n'en demande aucune : seule la
#: couleur est desactivee, pour que le rapport reste comparable d'une execution
#: a l'autre.
ENVIRONMENT: tuple[tuple[str, str], ...] = (("NO_COLOR", "1"),)


def commands(spec: Any, outdir: Path) -> list[Command]:
    """Commandes validant la supervision generee, dans l'ordre d'execution."""
    familles = spec.monitoring.family_names()
    liste: list[Command] = []

    for env in spec.service.environments:
        liste.append(
            Command(
                label=f"promtool check config ({env.name})",
                tool="promtool",
                argv=("check", "config", tree.config_file(env.name)),
                cwd=outdir,
                timeout=TIMEOUT,
                env=ENVIRONMENT,
                install_hint=INSTALL_HINT,
                requires_linux=True,
            )
        )
        liste.append(
            Command(
                label=f"promtool check rules ({env.name})",
                tool="promtool",
                argv=(
                    "check",
                    "rules",
                    # Les chemins sont enumeres plutot que glisses en glob : les
                    # commandes sont lancees sans shell, et un `*` non developpe
                    # ferait echouer promtool sur un fichier introuvable.
                    *(tree.rule_file(env.name, famille) for famille in familles),
                ),
                cwd=outdir,
                timeout=TIMEOUT,
                env=ENVIRONMENT,
                install_hint=INSTALL_HINT,
                requires_linux=True,
            )
        )

    for env in spec.service.environments:
        liste.append(
            Command(
                label=f"promtool test rules ({env.name})",
                tool="promtool",
                argv=(
                    "test",
                    "rules",
                    *(tree.test_file(env.name, famille) for famille in familles),
                ),
                cwd=outdir,
                timeout=TIMEOUT,
                env=ENVIRONMENT,
                install_hint=INSTALL_HINT,
                requires_linux=True,
            )
        )
    return liste
