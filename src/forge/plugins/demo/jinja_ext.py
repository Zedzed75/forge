"""Filtres propres au domaine `demo`.

Montre comment un plugin enrichit l'environnement Jinja de copier **sans**
toucher au coeur ni au copier.yml racine : il expose `FILTERS` et/ou `GLOBALS`,
que `forge.jinja_ext.ForgeExtension` charge a partir de la variable
d'environnement `FORGE_PLUGIN_JINJA` positionnee par le runner copier.
"""

from __future__ import annotations

#: Symbole affiche en tete de fichier selon le type de widget.
KIND_SYMBOLS = {"gauge": "~", "counter": "#", "log": ">"}


def shout(value: str) -> str:
    """Met une chaine en capitales : filtre temoin, verifie par les tests."""
    return str(value).upper()


def widget_symbol(kind: str) -> str:
    """Symbole associe a un type de widget, `?` si le type est inconnu."""
    return KIND_SYMBOLS.get(kind, "?")


def demo_banner(service_name: str) -> str:
    """Global temoin : prouve que `GLOBALS` d'un plugin est bien charge."""
    return f"== {service_name} =="


#: Filtres exposes aux gabarits du domaine demo.
FILTERS = {
    "shout": shout,
    "widget_symbol": widget_symbol,
}

#: Fonctions globales exposees aux gabarits du domaine demo.
GLOBALS = {
    "demo_banner": demo_banner,
}
