"""Constants and formats of the monitoring domain.

These checks exist because `promtool` does not do all of them, and the ones it
does, it does **after** generation. A malformed metric name is refused by
promtool; a well-formed but non-existent metric name produces a perfectly valid
and permanently mute rule. The model cannot check existence, but it can refuse
what is certainly wrong.
"""

from __future__ import annotations

import re
from typing import Final

#: Prometheus metric name. Colons are reserved for recording rules, but stay
#: syntactically valid.
METRIC_NAME_RE: Final[re.Pattern[str]] = re.compile(r"^[a-zA-Z_:][a-zA-Z0-9_:]*$")

#: Prometheus label name. The `__` prefix is reserved for Prometheus itself.
LABEL_NAME_RE: Final[re.Pattern[str]] = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

#: Prometheus duration: an integer followed by a unit. Prometheus also accepts
#: compound durations (`1h30m`); this simple form is enough here and reads better.
DURATION_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9]+(ms|[smhdwy])$")

#: Scrape target: `host:port`. The host may carry a name or an address.
TARGET_RE: Final[re.Pattern[str]] = re.compile(
    r"^[a-zA-Z0-9]([a-zA-Z0-9._-]*[a-zA-Z0-9])?:[0-9]{1,5}$"
)

#: URL probed by the blackbox exporter.
PROBE_URL_RE: Final[re.Pattern[str]] = re.compile(r"^https?://[^\s]+$")

#: Name of the external probe job, in the configuration as in the rules.
BLACKBOX_JOB: Final[str] = "blackbox"

#: Probe module of the blackbox exporter. `http_2xx` is the one of its default
#: configuration: any other name requires configuring the exporter accordingly.
BLACKBOX_MODULE: Final[str] = "http_2xx"

#: Values used by the generated unit tests. They need to exist nowhere: promtool
#: builds the series itself.
TEST_INSTANCE: Final[str] = "test-instance:9090"
TEST_POD: Final[str] = "test-pod"
TEST_CONTAINER: Final[str] = "test-container"
TEST_PROBE_URL: Final[str] = "https://test-probe.invalid"
