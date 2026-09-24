<!--
Thanks for the pull request. Fill in what applies and delete what does not —
this is a checklist, not a form to be completed literally.

Read CONTRIBUTING.md first if you have not. The rule that catches people out:
never commit to master, always branch and open a PR.
-->

## What this changes

<!-- One or two sentences. What was wrong, or what this adds. -->

## Why

<!--
The reasoning, not a restatement of the diff. If this fixes an issue, link it:
"Fixes #123".
-->

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] New or extended domain plugin
- [ ] Generated output changed (templates, defaults, comments)
- [ ] Documentation only
- [ ] Build, CI or packaging

## Generated output

<!--
Skip this section if the diff cannot change what forge generates.
-->

- [ ] This change does **not** alter generated output.
- [ ] This change **does** alter generated output. The golden tests under
      `tests/golden/` are updated in this PR, and the reason the output changed
      is explained below.

<!-- If output changed, explain what changed and why it is correct: -->

## Checks

- [ ] The full suite passes locally (`uv run pytest`).
- [ ] CI is green on all three supported Python versions.
- [ ] Generated projects still pass their domain's real validators
      (`ansible-lint`, `helm lint` + `kubeconform -strict`, `terraform validate`
      + `tflint`, `promtool test rules`, `actionlint`), or CI proves it.
- [ ] New or changed generated files are commented: a header explaining the
      file's purpose, explicit names on tasks/resources, a comment on every
      user-facing variable with its allowed values.
- [ ] Templates use the copier delimiters `[[ ]]` / `[% %]` / `[# #]`. No
      `{{ }}` used to mean "a generator variable".
- [ ] Core stayed domain-agnostic — no domain knowledge added under
      `src/forge/core/`.
- [ ] Commits are logical and self-contained; no unrelated reformatting mixed in.

## Anything reviewers should look at first

<!--
Point at the part you are least sure about, or the decision you would most like
challenged. A blank line here is fine, but a good answer saves a review round.
-->
