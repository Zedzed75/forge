---
name: Feature request
about: A capability forge does not have — a new option, a new domain, more generated output
title: ''
labels: enhancement
assignees: ''
---

## The problem

<!--
Describe the situation you are in, not the solution you have in mind. What are
you trying to generate, and what do you have to do by hand today because forge
will not do it?
-->

## What you would like forge to do

<!-- The behaviour you want. -->

## Which part of forge this touches

<!-- Tick what applies. -->

- [ ] An existing domain: <!-- ansible / helm / terraform / monitoring / pipeline -->
- [ ] A new domain plugin
- [ ] The spec model (`forge.yml`) — a new section, field or allowed value
- [ ] The CLI or the interview
- [ ] Generated output only (new file, more comments, different defaults)
- [ ] Something else:

## What the spec would look like

<!--
If this adds or changes something in forge.yml, sketch it. A concrete snippet
makes the proposal much easier to evaluate than a description.
-->

```yaml
# forge.yml
```

## What the generated output would look like

<!-- A sketch of the file(s) forge would produce, if that is the point. -->

## Constraints this has to respect

<!--
forge has rules that a feature cannot break. Please confirm you have considered
them, or explain why the feature needs an exception:

- Core stays domain-agnostic; domain knowledge lives only in plugins.
- Adding a domain must not require changes to core.
- Same spec => same output. Determinism is not negotiable.
- Generated projects must still pass their domain's real validators.
- Every generated file stays commented and readable.
- A domain is always optional: an absent section generates nothing.
-->

## Alternatives you considered

<!-- Including "do it by hand" or "use a different tool" — say why they fall short. -->

## Are you willing to implement it?

- [ ] Yes, with guidance on where it should live
- [ ] Yes, I already know where it goes
- [ ] No, I am proposing it
