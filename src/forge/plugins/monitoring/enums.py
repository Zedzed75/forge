"""Enumerations of the monitoring domain."""

from __future__ import annotations

from enum import Enum


class Severity(str, Enum):
    """Severity carried by the `severity` label of an alert.

    Two levels, not five: a fine-grained scale does not survive the first month
    of on-call duty. The question is binary — does somebody have to get up now?
    """

    #: The service is degraded or unavailable: wake somebody up.
    CRITICAL = "critical"

    #: The service works but something is going to end badly: look tomorrow.
    WARNING = "warning"


class RuleFamily(str, Enum):
    """Families of alerting rules the domain can generate.

    The declaration order is the canonical order: it fixes the order of the rule
    files, that of the lines of the README and that of the keys of
    `domain.rule_slots`.

    It follows the progression of a diagnosis: does the service answer? does it
    answer correctly? does it answer quickly? does it have enough to keep going?
    is it holding up? is it reachable from the outside?
    """

    #: The target no longer answers at all (`up == 0`).
    AVAILABILITY = "availability"

    #: Too many responses in error.
    ERROR_RATE = "error_rate"

    #: Responses too slow (95th percentile of the response time).
    LATENCY = "latency"

    #: Consumption close to the limits (CPU, memory).
    SATURATION = "saturation"

    #: Containers restarting in a loop.
    RESTARTS = "restarts"

    #: External probe: is the service reachable, is its certificate holding?
    PROBE = "probe"
