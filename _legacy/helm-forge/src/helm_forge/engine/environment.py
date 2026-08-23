"""Fabrique de l'environnement Jinja2 du générateur.

Point central de la convention posée par ``CLAUDE.md`` : Helm et Jinja2
utilisent tous deux ``{{ }}``. Le générateur adopte donc des délimiteurs
distincts, de sorte que la syntaxe Helm traverse les gabarits sans être
interprétée ni échappée.

    Jinja2 (générateur)        Helm (chart généré)
    [[ variable ]]             {{ .Values.foo }}
    [% for x in y %]           {{- range .Values.list }}
    [# commentaire #]          {{/* commentaire */}}
"""

from __future__ import annotations

from jinja2 import Environment, PackageLoader, StrictUndefined

from .filters import FILTERS

#: Délimiteurs personnalisés, à ne jamais modifier sans reprendre l'intégralité
#: des gabarits.
JINJA_DELIMITERS = {
    "block_start_string": "[%",
    "block_end_string": "%]",
    "variable_start_string": "[[",
    "variable_end_string": "]]",
    "comment_start_string": "[#",
    "comment_end_string": "#]",
}


def build_environment() -> Environment:
    """Construit l'environnement Jinja2 utilisé pour tous les rendus.

    ``StrictUndefined`` est délibéré : une variable absente doit faire échouer
    la génération, jamais produire un trou silencieux dans un manifeste.
    """
    env = Environment(
        loader=PackageLoader("helm_forge", "templates"),
        undefined=StrictUndefined,
        # trim_blocks et lstrip_blocks évitent les lignes vides parasites
        # laissées par les balises de contrôle, qui pollueraient le YAML rendu.
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
        # Aucun échappement : on produit du YAML et du texte, pas du HTML.
        autoescape=False,
        **JINJA_DELIMITERS,
    )
    env.filters.update(FILTERS)
    return env
