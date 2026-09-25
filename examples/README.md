# Examples

**A project does not need everything.** It may need only a Helm chart, or only
Ansible roles and playbooks, or only a Terraform foundation. This directory
shows the six cases, and what tells them apart is the user's choice — nothing
else.

| Example | Produces | For whom |
| --- | --- | --- |
| [`ansible-only.yml`](ansible-only.yml) | `ansible/` | machines to configure, no container |
| [`helm-only.yml`](helm-only.yml) | `helm/` | a cluster that already exists, a service to package |
| [`terraform-only.yml`](terraform-only.yml) | `terraform/` | a platform team preparing the ground |
| [`monitoring-only.yml`](monitoring-only.yml) | `monitoring/` | an already deployed service, missing only the knowledge of when it goes wrong |
| [`pipeline-only.yml`](pipeline-only.yml) | `.github/workflows/` | a repository that needs nothing but a CI chain |
| [`foundation-and-chart.yml`](foundation-and-chart.yml) | `terraform/` **and** `helm/` | the foundation and what sits on it, together |

```bash
forge generate -s examples/helm-only.yml -o /tmp/storefront
```

## How the choice is made

Three ways, and they combine:

**1. An absent section generates nothing.** That is the basic mechanism, with no
exception. `ansible-only.yml` contains no `helm:` section: no chart is produced.
There is no option to pass, no flag to turn off.

**2. `--only` restricts one run.** On a project declaring two domains, to
regenerate just one of them:

```bash
forge generate -s examples/foundation-and-chart.yml -o /tmp/inventory --only helm
```

`--only` always restricts, it never adds: asking for a domain the specification
does not declare will not make it appear.

**3. The interview asks which ones to produce.** `forge new` asks the question
before writing anything, and then only asks about the domains you kept.

```bash
forge new -o /tmp/my-service
```

## Knowing what will come out, before it comes out

```bash
forge plugins -s examples/helm-only.yml
```

says, for that specification, which domains are requested and which are not. And
`forge generate --dry-run` announces what it would produce without writing
anything.

If a specification declares no domain, forge does not silently produce an empty
project: it says which ones are available and how to ask for one.

## The pipeline is the domain that federates the others

The `pipeline` domain is the only one whose output **depends on the other
sections**. It emits one validation job per declared domain, with the commands
each domain announces itself and the installation of the tools they require.

Add a `helm:` section to [`pipeline-only.yml`](pipeline-only.yml) and a
"Validate Helm" job appears, without a single template line changing. It invents
nothing for all that: a domain that does not say how to deploy itself is
**named** in the emitted file, not guessed.

It is also the only domain whose output is the repository root — a CI file only
exists where its tool reads it.

## Adding a domain to an existing project

Add its section to `forge.yml`, then:

```bash
forge generate --only terraform
```

The already generated domains are left untouched. Conversely, removing a section
erases nothing: forge has never deleted a file you may have edited — `forge
diff` shows you the difference, the deletion stays yours.

## These examples are tested

`tests/test_domain_selection.py` generates each of these files and checks that
it produces exactly the domains it declares, no more and no less. It also checks
that **a single-domain example exists for every shipped domain**: a domain added
without one makes the suite fail. A stale example is not possible here.
