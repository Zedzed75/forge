# Security Policy

## Supported versions

forge is a young project with a single active line of development. Security
fixes are applied to `master` and released in the next version; there are no
maintained backport branches.

| Version | Supported |
| --- | --- |
| Latest release / `master` | Yes |
| Anything older | No — upgrade first |

## Reporting a vulnerability

**Please do not open a public issue for a security problem.**

Report it privately through GitHub's private vulnerability reporting:

1. Go to https://github.com/Zedzed75/forge/security/advisories/new
2. Describe the issue and how to reproduce it.

That channel is private between you and the maintainers until an advisory is
published. If it is unavailable to you for any reason, open a public issue
containing only the sentence "I would like to report a security issue
privately" and no technical detail, and you will be contacted to arrange a
private channel.

### What to include

- A description of the problem and why you believe it is a security issue.
- The smallest `forge.yml` spec or command sequence that reproduces it.
- The forge version (`forge --version`), Python version, and operating system.
- The impact as you understand it, and any suggested fix.

### Response window

This project is maintained on a best-effort basis by a small number of people.
Realistically:

- **Acknowledgement within 7 days** that the report was received and read.
- **An initial assessment within 30 days** — whether it is accepted as a
  vulnerability, and if so a rough severity and plan.
- Fixes are shipped as soon as practical after that. A fix for a confirmed
  high-severity issue takes priority over other work.

If you have not heard anything after 7 days, please send a reminder — it means
the notification was missed, not that the report was ignored.

### Disclosure

We ask for **90 days** between the report and public disclosure, or until a fix
is released, whichever comes first. If we cannot fix an issue in that window we
will say so and agree a new date with you rather than let the clock run out
silently. Reporters are credited in the advisory unless they ask not to be.

## Scope

forge is a code generator. It reads a `forge.yml` spec you provide and writes
an infrastructure project to a directory you choose. Things that are in scope:

- Anything that lets a crafted `forge.yml` execute code, write outside the
  chosen output directory, or read files it was not pointed at.
- Template injection or escaping bugs that cause forge to emit an insecure
  generated project from a benign spec.
- Insecure defaults in generated output — for example a generated manifest that
  grants more privilege than the spec asked for.
- Credentials or secrets leaking into generated files, logs, or error messages.

Out of scope:

- Vulnerabilities in the tools forge generates configuration *for* (Ansible,
  Helm, Terraform, Prometheus, GitHub Actions, GitLab CI). Report those
  upstream.
- Vulnerabilities in third-party dependencies with no forge-specific impact —
  report upstream; we will pick up the version bump.
- Insecure infrastructure that forge produced because the spec explicitly asked
  for it. forge does what the spec says.
- Results from automated scanners with no demonstrated exploit path.

Thank you for reporting responsibly.
