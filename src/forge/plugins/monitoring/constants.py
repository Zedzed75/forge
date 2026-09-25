"""Constantes et formats du domaine monitoring.

Ces controles existent parce que `promtool` ne les fait pas tous, et que ceux
qu'il fait, il les fait **apres** la generation. Un nom de metrique mal forme
est refuse par promtool ; un nom de metrique bien forme mais inexistant produit
une regle parfaitement valide et definitivement muette. Le modele ne peut pas
verifier l'existence, mais il peut refuser ce qui est certainement faux.
"""

from __future__ import annotations

import re
from typing import Final

#: Nom de metrique Prometheus. Les deux-points sont reserves aux regles
#: d'enregistrement, mais restent syntaxiquement valides.
METRIC_NAME_RE: Final[re.Pattern[str]] = re.compile(r"^[a-zA-Z_:][a-zA-Z0-9_:]*$")

#: Nom de libelle Prometheus. Le prefixe `__` est reserve a Prometheus lui-meme.
LABEL_NAME_RE: Final[re.Pattern[str]] = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

#: Duree Prometheus : un entier suivi d'une unite. Prometheus accepte aussi les
#: durees composees (`1h30m`) ; cette forme simple suffit ici et se lit mieux.
DURATION_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9]+(ms|[smhdwy])$")

#: Cible de collecte : `hote:port`. L'hote peut porter un nom ou une adresse.
TARGET_RE: Final[re.Pattern[str]] = re.compile(
    r"^[a-zA-Z0-9]([a-zA-Z0-9._-]*[a-zA-Z0-9])?:[0-9]{1,5}$"
)

#: URL sondee par le blackbox exporter.
PROBE_URL_RE: Final[re.Pattern[str]] = re.compile(r"^https?://[^\s]+$")

#: Nom du job de sonde externe, dans la configuration comme dans les regles.
BLACKBOX_JOB: Final[str] = "blackbox"

#: Module de sonde du blackbox exporter. `http_2xx` est celui de sa
#: configuration par defaut : n'importe quel autre nom exige de configurer
#: l'exporter en consequence.
BLACKBOX_MODULE: Final[str] = "http_2xx"

#: Valeurs employees par les tests unitaires engendres. Elles n'ont besoin
#: d'exister nulle part : promtool fabrique les series lui-meme.
TEST_INSTANCE: Final[str] = "test-instance:9090"
TEST_POD: Final[str] = "test-pod"
TEST_CONTAINER: Final[str] = "test-container"
TEST_PROBE_URL: Final[str] = "https://test-probe.invalid"
