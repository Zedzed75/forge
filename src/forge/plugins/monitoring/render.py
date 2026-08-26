"""Resolution des jetons du catalogue, et projection d'une alerte.

Deux substitutions, et la seconde est le point interessant :

1. les jetons `@…@` du catalogue deviennent les valeurs de la specification ;
2. les references `{{ $labels.<nom> }}` d'une annotation sont resolues avec les
   libelles du test unitaire, pour produire l'annotation **telle que promtool la
   verra**.

La seconde evite la seule duplication dangereuse de ce domaine. `promtool test
rules` compare les annotations rendues caractere par caractere : ecrire a la
main, dans le fichier de test, ce que l'annotation est censee donner ferait
diverger la regle et son test au premier changement de formulation — et un test
qui verifie une ancienne formulation ne verifie plus rien.
"""

from __future__ import annotations

from typing import Any

from forge.plugins.monitoring.catalog.alerts import Alert


def substitute(text: str, values: dict[str, Any]) -> str:
    """Remplace les jetons `@cle@` de `text` par les valeurs fournies.

    Ni `str.format` ni `string.Template` ne conviennent : PromQL est plein
    d'accolades (`{job="x"}`) et les annotations sont pleines de `$`
    (`{{ $labels.pod }}`).
    """
    for cle, valeur in values.items():
        text = text.replace(f"@{cle}@", format_number(valeur))
    return text


def format_number(value: Any) -> str:
    """Rend un nombre de facon **identique** dans l'expression et le texte.

    `1.0` s'ecrit `1`, `0.05` s'ecrit `0.05`. Sans cette normalisation, une
    expression PromQL dirait `> 1.0` et l'annotation « depasse 1 seconde », ce
    qui suffirait a rendre le test unitaire faux.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return str(value)
    if float(value).is_integer():
        return str(int(value))
    return repr(round(float(value), 10))


def percent(value: float) -> str:
    """Rend une proportion en pourcentage, sans artefact de virgule flottante."""
    return format_number(round(value * 100, 6))


def render_description(description: str, labels: dict[str, str]) -> str:
    """Resout `{{ $labels.<nom> }}` avec les libelles donnes.

    Un libelle absent est laisse tel quel : le test unitaire echouera alors en
    montrant la reference non resolue, ce qui est exactement le diagnostic
    voulu — l'alerte cite un libelle que son expression ne produit pas.
    """
    rendu = description
    for nom, valeur in labels.items():
        rendu = rendu.replace("{{ $labels." + nom + " }}", valeur)
    return rendu


def project(
    alert: Alert,
    values: dict[str, Any],
    *,
    alert_prefix: str,
    rule_labels: dict[str, str],
) -> dict[str, Any]:
    """Projette une alerte du catalogue en dict JSON-serialisable.

    Le dict porte la regle **et** son test unitaire : les deux sont construits
    a partir des memes valeurs, dans la meme fonction, ce qui les empeche de
    diverger.
    """
    resolus = dict(values)
    if alert.threshold_field:
        seuil = resolus.get(alert.threshold_field, alert.threshold_default)
        resolus["threshold"] = seuil
        resolus["threshold_pct"] = percent(float(seuil))

    summary = substitute(alert.summary, resolus)
    description = substitute(alert.description, resolus)
    libelles_resultat = {
        nom: substitute(valeur, resolus)
        for nom, valeur in alert.test_result_labels.items()
    }

    return {
        "name": f"{alert_prefix}{alert.name}",
        "expr": substitute(alert.expr, resolus),
        "for": alert.for_duration,
        "severity": alert.severity.value,
        "summary": summary,
        "description": description,
        "labels": dict(rule_labels),
        "threshold_field": alert.threshold_field or "",
        "threshold": format_number(resolus.get("threshold", "")) if alert.threshold_field else "",
        "threshold_unit": alert.threshold_unit,
        "test": {
            "series": [
                {
                    "series": substitute(serie, resolus),
                    # Surtout pas `values` : en Jinja, `serie.values` resoudrait
                    # la methode du dict avant la cle, et le gabarit ecrirait
                    # `<built-in method values...>` dans le fichier de test.
                    # promtool s'en plaint, mais tres loin de la cause.
                    # Les points portent des jetons eux aussi : le pas d'un
                    # compteur est calcule a partir du seuil.
                    "points": substitute(valeurs, resolus),
                }
                for serie, valeurs in alert.test_series
            ],
            "eval_time": alert.test_eval_time,
            # Ce que promtool doit retrouver : les libelles que la regle ajoute,
            # plus ceux que l'expression laisse survivre.
            "exp_labels": {**rule_labels, **libelles_resultat},
            "exp_annotations": {
                "summary": summary,
                "description": render_description(description, libelles_resultat),
            },
        },
    }


def alert_prefix(service_name: str) -> str:
    """Prefixe des noms d'alerte, derive du nom du service.

    `boutique` -> `Boutique`, `db-proxy` -> `DbProxy`. Un nom d'alerte est un
    identifiant en CamelCase par convention Prometheus, et le prefixer par le
    service evite qu'une alerte `CibleInjoignable` de deux services differents
    se confonde dans un recepteur commun.
    """
    return "".join(morceau.capitalize() for morceau in service_name.replace("_", "-").split("-"))
