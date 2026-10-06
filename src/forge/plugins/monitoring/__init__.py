"""Monitoring domain plugin: probes, alerting rules and their tests.

A self-contained domain: it reads **no** other section of forge.yml. What it
watches, it declares itself; coherence with the other domains goes through the
facet vocabulary (`namespaces`, `ingress_hosts`), checked by `forge validate`. It
is the same mechanism as for Helm and Terraform, and it asks for no coupling.

What is specific to this domain: `promtool` can run **alert unit tests** — give
it a synthetic time series and check that the alert fires with the right labels.
forge generates one per rule family. An untested alerting rule is a rule nobody
knows fires or not, and that is only learnt the day it should have.
"""
