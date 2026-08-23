"""Extension Jinja2 chargee par copier (`_jinja_extensions` du copier.yml racine).

copier n'accepte pas de filtres passes en Python : seule une extension
importable peut enrichir son environnement (MIGRATION.md §2.2). Ce module
concentre donc les filtres communs, issus de la fusion des deux tables legacy
(MIGRATION.md §5.5) :

* `yaml_scalar`, `yaml_assign`, `comment`, `lower_first`, `rule` — d'ansible-forge ;
* `to_yaml`, `yaml_value`, `indent_block` — de helm-forge.

Arbitrage des deux implementations divergentes :

* `yaml_scalar` : version ansible-forge retenue (elle accepte tout scalaire, pas
  seulement les chaines ; rendu identique sur les chaines).
* `comment` : version ansible-forge retenue (elle preserve l'indentation de la
  ligne source et rend les lignes vides en `#`), completee par le parametre
  `prefix` de helm-forge. Signature : `comment(text, indent=0, width=88,
  prefix="# ")` ; les gabarits helm qui passaient la largeur en 2e position
  devront la nommer (`| comment(width=76)`).

Un plugin ajoute ses propres filtres sans toucher au coeur : il fournit un
module `forge.plugins.<domaine>.jinja_ext` exposant `FILTERS` et/ou `GLOBALS`,
que le runner copier declare via la variable d'environnement
`FORGE_PLUGIN_JINJA` (cf. `forge.render.copier_runner`).
"""

from __future__ import annotations

import importlib
import os
import textwrap
from typing import Any

import yaml
from jinja2.ext import Extension

#: Largeur maximale d'une ligne de commentaire generee.
COMMENT_WIDTH = 88

#: Largeur des filets de separation des en-tetes.
RULE_WIDTH = 75

#: Variable d'environnement listant les modules de filtres de plugin.
PLUGIN_JINJA_ENV_VAR = "FORGE_PLUGIN_JINJA"


class _BlockDumper(yaml.SafeDumper):
    """Dumper YAML indentant les listes sous leur cle parente."""

    def increase_indent(self, flow: bool = False, indentless: bool = False) -> Any:
        return super().increase_indent(flow, False)


def _plain(value: Any) -> Any:
    """Convertit recursivement les objets non natifs en types YAML surs."""
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float, str)):
        return value
    return str(value)


def yaml_scalar(value: Any) -> str:
    """Rend une valeur scalaire en YAML, avec les guillemets necessaires.

    Passe par le dump d'une paire cle/valeur : c'est PyYAML qui decide de la
    citation, ce qui evite toute divergence avec le parseur cible. `api` reste
    nu ; `1.36`, `true` ou `on` sont proteges.
    """
    dumped = yaml.dump(
        {"_": _plain(value)},
        Dumper=_BlockDumper,
        default_flow_style=False,
        allow_unicode=True,
        width=10**6,
        sort_keys=False,
    )
    return dumped.rstrip("\n").removeprefix("_: ")


def to_yaml(value: Any, indent: int = 0) -> str:
    """Rend une valeur Python en YAML, prete a etre inseree dans un gabarit.

    Scalaires sur une ligne, listes et dictionnaires en blocs indentes de
    `indent` espaces. L'ordre des cles suit l'ordre d'insertion, jamais l'ordre
    alphabetique : c'est ce qui rend le rendu reproductible.
    """
    if not isinstance(value, (list, tuple, dict)):
        return yaml_scalar(value)
    if not value:
        # Collection vide : la forme en ligne est plus lisible qu'un bloc vide.
        return "[]" if isinstance(value, (list, tuple)) else "{}"
    text = yaml.dump(
        _plain(value),
        Dumper=_BlockDumper,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        width=100,
    ).rstrip("\n")
    return textwrap.indent(text, " " * indent) if indent else text


def yaml_value(value: Any, indent: int = 0) -> str:
    """Rend une valeur destinee a figurer a droite d'une cle YAML.

    Une collection non vide ne peut pas rester sur la ligne de sa cle : YAML
    refuse `drop: - ALL`. Le filtre bascule donc en bloc indente, tandis que
    scalaires et collections vides restent en ligne. Il produit lui-meme le
    separateur, espace ou saut de ligne ; le gabarit colle la balise au
    deux-points (`drop:[[ items | yaml_value(8) ]]`) pour ne jamais laisser
    d'espace en fin de ligne.
    """
    if isinstance(value, (list, tuple, dict)) and value:
        return "\n" + to_yaml(value, indent=indent)
    return " " + to_yaml(value)


def yaml_assign(value: Any, indent: int = 0) -> str:
    """Variante de `yaml_value` qui bascule aussi les scalaires multi-lignes.

    A utiliser ainsi : `[[ name ]]:[[ value | yaml_assign(2) ]]`.
    """
    if isinstance(value, (list, tuple, dict)) and not value:
        return " []" if isinstance(value, (list, tuple)) else " {}"
    if not isinstance(value, (list, tuple, dict)):
        scalar = yaml_scalar(value)
        if "\n" not in scalar:
            return f" {scalar}"
    dumped = yaml.dump(
        _plain(list(value) if isinstance(value, tuple) else value),
        Dumper=_BlockDumper,
        default_flow_style=False,
        allow_unicode=True,
        width=10**6,
        sort_keys=False,
    ).rstrip("\n")
    pad = " " * indent
    return "\n" + "\n".join(f"{pad}{line}" if line else "" for line in dumped.splitlines())


def comment(
    text: str, indent: int = 0, width: int = COMMENT_WIDTH, prefix: str = "# "
) -> str:
    """Transforme un texte en bloc de commentaires, replie a `width`.

    Les lignes vides du texte source deviennent des lignes `#` isolees, ce qui
    permet d'ecrire des paragraphes dans les descriptions de catalogue.
    L'indentation d'une ligne source est conservee : elle porte du sens dans les
    exemples de commandes cites en en-tete de fichier.
    """
    pad = " " * indent
    available = max(width - indent - len(prefix), 20)
    lines: list[str] = []
    for paragraph in text.split("\n"):
        stripped = paragraph.strip()
        if not stripped:
            lines.append(f"{pad}{prefix}".rstrip())
            continue
        lead = paragraph[: len(paragraph) - len(paragraph.lstrip())]
        chunks = textwrap.wrap(
            stripped, width=available, initial_indent=lead, subsequent_indent=lead
        )
        lines.extend(f"{pad}{prefix}{chunk}".rstrip() for chunk in chunks)
    return "\n".join(lines)


def indent_block(text: str, spaces: int, first: bool = False) -> str:
    """Indente un bloc de texte deja rendu.

    `first` a faux laisse la premiere ligne intacte, cas courant ou le gabarit a
    deja ecrit l'indentation de depart.
    """
    if not text:
        return text
    indented = textwrap.indent(text, " " * spaces)
    return indented if first else indented[spaces:]


def lower_first(text: str) -> str:
    """Met la premiere lettre en minuscule, pour enchainer apres un deux-points.

    N'affecte pas les textes commencant par un sigle ou un nom propre en
    majuscules (`UTF8`, `Ansible`), reconnus a leur deuxieme lettre.
    """
    if len(text) >= 2 and text[1].isupper():
        return text
    return text[:1].lower() + text[1:]


def rule(width: int = RULE_WIDTH) -> str:
    """Retourne un filet de separation en commentaire."""
    return "# " + "-" * width


#: Filtres exposes aux gabarits, sous le nom employe dans les `| filtre`.
FILTERS = {
    "yaml_scalar": yaml_scalar,
    "yaml_assign": yaml_assign,
    "yaml_value": yaml_value,
    "to_yaml": to_yaml,
    "comment": comment,
    "indent_block": indent_block,
    "lower_first": lower_first,
}

#: Fonctions globales exposees aux gabarits.
GLOBALS = {
    "rule": rule,
}


def plugin_tables(dotted_paths: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Charge les tables `FILTERS`/`GLOBALS` des modules cites, dans l'ordre."""
    filters: dict[str, Any] = {}
    globals_: dict[str, Any] = {}
    for dotted in (part.strip() for part in dotted_paths.split(",")):
        if not dotted:
            continue
        module = importlib.import_module(dotted)
        filters.update(getattr(module, "FILTERS", {}))
        globals_.update(getattr(module, "GLOBALS", {}))
    return filters, globals_


class ForgeExtension(Extension):
    """Injecte les filtres de forge dans l'environnement Jinja2 de copier."""

    def __init__(self, environment: Any) -> None:
        super().__init__(environment)
        environment.filters.update(FILTERS)
        environment.globals.update(GLOBALS)
        extra_filters, extra_globals = plugin_tables(
            os.environ.get(PLUGIN_JINJA_ENV_VAR, "")
        )
        environment.filters.update(extra_filters)
        environment.globals.update(extra_globals)
