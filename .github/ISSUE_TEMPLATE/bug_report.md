---
name: Bug report
about: Something forge does wrong, or generated output that is wrong or invalid
title: ''
labels: bug
assignees: ''
---

<!--
Security issues do NOT belong here. See SECURITY.md for the private channel.
-->

## What happened

<!-- What forge did. Be concrete. -->

## What you expected instead

<!-- What it should have done, and why. -->

## The spec that reproduces it

<!--
This is the single most useful thing you can provide. Reduce your forge.yml to
the smallest version that still shows the problem, and paste it whole. Remove
anything confidential — forge never needs real hostnames or credentials to
reproduce a generation bug.
-->

```yaml
# forge.yml
```

## The command you ran

```bash
forge generate -s forge.yml -o /tmp/out
```

## Output

<!--
Paste the error and traceback, or the generated file that is wrong. If a
validator rejected the generated project, paste the validator's message too
(ansible-lint, helm lint, kubeconform, terraform validate, promtool,
actionlint...). Trim it to the relevant part rather than pasting hundreds of
lines.
-->

```
```

## Environment

- forge version (`forge --version`):
- Python version (`python --version`):
- Operating system:
- Domain(s) involved (ansible / helm / terraform / monitoring / pipeline):
- Relevant validator versions, if the bug is about generated output being rejected:

## Anything else

<!--
Does it reproduce every time, or intermittently? Did it work in an earlier
version? Anything you already ruled out?
-->
