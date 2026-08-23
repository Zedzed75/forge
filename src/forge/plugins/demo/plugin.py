"""Plugin `demo` — banc d'essai du contrat de plugin, reserve aux tests.

Il n'est pas enregistre par defaut (`BUILTIN_PLUGINS` est vide) : les tests le
declarent via `FORGE_PLUGINS=forge.plugins.demo.plugin`. Sa raison d'etre est
d'exercer, des la phase 2, les mecanismes que les vrais plugins utiliseront en
phases 3 et 4 :

* balises `yield` **imbriquees** (environnement x widget) dans les chemins ;
* filtre de plugin injecte par extension Jinja (`forge.plugins.demo.jinja_ext`) ;
* filtrage de fichier par `[% if %]` sur un segment de chemin ;
* commande de validation externe, avec repli d'outil absent.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import Field, field_validator

from forge.interview.prompter import Prompter
from forge.plugins_api.hookspecs import hookimpl
from forge.plugins_api.types import CatalogEntry, Command, DomainInfo, Projection
from forge.spec.names import require_unique
from forge.spec.service import ServiceSpec
from forge.spec.types import DnsLabel, ForgeModel

#: Types de widgets reconnus par le domaine de demonstration.
WIDGET_KINDS = ("gauge", "counter", "log")


class DemoWidget(ForgeModel):
    """Un widget a materialiser dans chaque environnement."""

    #: Nom du widget : label DNS, sert de nom de fichier.
    name: DnsLabel

    #: Type de widget ; determine le contenu genere.
    kind: str = "gauge"

    #: Marque un widget produisant un fichier supplementaire (test du `[% if %]`).
    detailed: bool = False

    @field_validator("kind")
    @classmethod
    def _known_kind(cls, value: str) -> str:
        if value not in WIDGET_KINDS:
            raise ValueError(f"type inconnu : {value} (attendu : {', '.join(WIDGET_KINDS)})")
        return value


class DemoSpec(ForgeModel):
    """Section `demo:` de forge.yml."""

    #: Widgets a generer, dans l'ordre de declaration.
    widgets: list[DemoWidget] = Field(min_length=1)

    #: Salutation reprise dans l'en-tete des fichiers generes.
    greeting: str = "bonjour"

    @field_validator("widgets")
    @classmethod
    def _unique_names(cls, value: list[DemoWidget]) -> list[DemoWidget]:
        require_unique((widget.name for widget in value), "noms de widget")
        return value


@hookimpl
def forge_domain() -> DomainInfo:
    return DomainInfo(
        name="demo",
        title="Demo",
        summary="Domaine de demonstration, utilise par les tests du coeur",
    )


@hookimpl
def forge_spec_model() -> type[DemoSpec]:
    return DemoSpec


@hookimpl
def forge_template_subdir() -> str:
    return "src/forge/plugins/demo/template"


@hookimpl
def forge_answers(spec: Any) -> dict[str, Any]:
    """Projette la spec vers le dict `domain`, avec un ordre de cles figé."""
    demo: DemoSpec = spec.demo
    return {
        "greeting": demo.greeting,
        "environments": [
            {"name": env.name, "production": env.production}
            for env in spec.service.environments
        ],
        "widgets": [
            {"name": widget.name, "kind": widget.kind, "detailed": widget.detailed}
            for widget in demo.widgets
        ],
    }


@hookimpl
def forge_projection(spec: Any) -> Projection:
    return Projection(
        service_name=spec.service.name,
        environments=tuple(env.name for env in spec.service.environments),
        labels=dict(spec.service.labels),
        facets={"widgets": tuple(widget.name for widget in spec.demo.widgets)},
    )


@hookimpl
def forge_validators(spec: Any, outdir: Path) -> list[Command]:
    """Une commande volontairement banale : le domaine demo ne valide rien de reel."""
    return [
        Command(
            label="demo : version de git",
            tool="git",
            argv=("--version",),
            cwd=outdir,
            install_hint="installez git et ajoutez-le au PATH",
        )
    ]


@hookimpl
def forge_catalog() -> list[CatalogEntry]:
    return [
        CatalogEntry(
            name=kind,
            summary=f"Widget de type {kind}",
            details=f"Genere un fichier par environnement pour un widget {kind}.",
            options={"detailed": "ajoute un fichier de detail par widget"},
        )
        for kind in WIDGET_KINDS
    ]


@hookimpl
def forge_interview(prompter: Prompter, service: ServiceSpec) -> dict[str, Any] | None:
    """Entretien minimal : sert a verifier le cablage du hook, pas l'ergonomie.

    Le coeur a deja demande *quels* domaines generer : le plugin ne le redemande
    pas. Il decline en retournant None, ici si aucun widget n'est nomme.
    """
    greeting = prompter.text("Salutation des en-tetes", default="bonjour")
    names = prompter.text("Widgets, separes par des virgules", default="cpu,memoire")
    widgets = []
    for name in (part.strip() for part in names.split(",")):
        if not name:
            continue
        kind = prompter.select(
            f"Type du widget {name}",
            choices=[(kind, kind) for kind in WIDGET_KINDS],
            default="gauge",
        )
        widgets.append({"name": name, "kind": kind})
    if not widgets:
        return None
    return {"greeting": greeting, "widgets": widgets}
