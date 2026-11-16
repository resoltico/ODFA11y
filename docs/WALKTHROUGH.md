# Worked source-to-evidence example

This example uses the supplied [invented report HTML](examples/report-source.html), unchanged.
It deliberately references an unavailable `chart.png`; a meaningful description alone cannot
establish the missing graphic or make native export safe. No result below certifies accessibility.

## Capture the actual source

From a restored checkout with supported LibreOffice on PATH, choose a new directory:

```sh
odfa11y_work=/absolute/new-fieldtest
mkdir "$odfa11y_work"
soffice "-env:UserInstallation=file://$odfa11y_work/profile" --headless \
  --convert-to odt --outdir "$odfa11y_work" docs/examples/report-source.html
uv run --no-sync odfa11y audit "$odfa11y_work/report-source.odt" --format json
uv run --no-sync odfa11y plan "$odfa11y_work/report-source.odt" > "$odfa11y_work/plan.toml"
```

On the measured LibreOffice 26.8.3.1/macOS run this produced **3 blocks, 30 lines**, compared
with the design-pass baseline of 23 blocks and 184 lines. Source audit exited 2; plan exited 0.
The questions concern the first structural heading, an undescribed graphic and a plain URL.
No speculative language-answer blocks appear. Native output and bindings can differ with
other producers: always generate your own plan rather than copying these fingerprints.

The real template contains live identities and inert answers, for example:

```toml
# HEADING002 error: "Heading hierarchy starts at level 3; expected level 1."
# h, "Sampling sites"
[decisions."heading.level"."content/heading[1]"]
# Current: {"level": "3"}
fingerprint = "339911db36884cc9"
# level = 1  # Intended outline level.
```

## Review answers and inspect the prediction

Save a separate `reviewed.toml`, retaining its generated source hash/fingerprints. The field
experiment supplied the original reviewed example's three answers:

```toml
# In the existing heading block:
level = 2
# In the existing graphic.alternative block:
description = "Bar chart: turbidity is low at all sites."
# In the existing text.linkify_addresses block:
enabled = true
```

The description is an example human answer, not a machine assessment of an unavailable chart.
The other fields stay commented. Unanswered blocks change nothing; empty alternative text
is not an accepted way to express a decorative role.

```sh
uv run --no-sync odfa11y remediate "$odfa11y_work/report-source.odt" \
  "$odfa11y_work/reviewed.odt" --plan "$odfa11y_work/reviewed.toml" --dry-run --format json
```

The measured preview exited 0, published nothing and predicted:

```text
heading.level: remaining HEADING002
```

Changing the first heading from level 3 to level 2 does not supply a preceding level 1.
Inspect the source hierarchy and decide the correct fix; an applied edit is not proof that
its finding disappeared. Other predictions resolved the undescribed-graphic and plain-URL
findings. The [plan reference](PLAN.md) explains bindings and unanswered/stale blocks.

## Publish the guarded candidate and retain evidence

```sh
uv run --no-sync odfa11y remediate "$odfa11y_work/report-source.odt" \
  "$odfa11y_work/reviewed.odt" --plan "$odfa11y_work/reviewed.toml" --format json
uv run --no-sync odfa11y run "$odfa11y_work/report-source.odt" \
  --plan "$odfa11y_work/reviewed.toml" --output-dir "$odfa11y_work/evidence-pdf" \
  --profile pdf --format json
uv run --no-sync odfa11y verify-evidence "$odfa11y_work/evidence-pdf" --format json
```

Remediation exited 0 and published the candidate after guards. The PDF run exited 2:
its candidate re-audit retained `HEADING002`; source/candidate export both refused the
unembedded chart resource. Dependent PDF/fidelity stages were skipped for missing inputs.
Integrity verification exited 0. Those outcomes distinguish successful guarded source edits,
remaining accessibility errors, refused native work and intact evidence.

Open `REVIEW.md`: outstanding human work comes first, the checklist reflects observed
source topics, and facts appear once as source → candidate. Embed/review the actual chart
in the authoring application and generate a newly bound plan before attempting distribution.

Without veraPDF, the production preparation control is:

```sh
uv run --no-sync odfa11y run "$odfa11y_work/report-source.odt" \
  --plan "$odfa11y_work/reviewed.toml" --output-dir "$odfa11y_work/evidence-production" \
  --profile production
```

It exited **3**, reported that veraPDF was not on PATH and created no production directory.
A selected executable does not make independent validation optional. See
[profiles](WORKFLOW.md#retain-evidence) and [evidence semantics](EVIDENCE.md).
