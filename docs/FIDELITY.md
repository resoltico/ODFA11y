# Fidelity comparison

```sh
odfa11y compare original.odt reviewed.odt --diff-dir differences --plan plan.toml
```

Each input is captured once. ODF inputs use one resolved LibreOffice and shared private
profile; PDFs use the bounded reader. Private export cannot establish filename/path fields
or relative hyperlink destinations: see [native context](ACCESSIBILITY.md#native-document-context-and-declared-dependencies).
Text and external URI targets always gate independently of accessibility checks.

## Set the policy

```toml
[fidelity]
pagination = "same"
raster_tolerance = 0.15
ink_threshold = 200
```

`Pagination.SAME(...)` retains page geometry and ink checks. Its tolerance must be finite
and nonnegative; threshold is an integer 0–255. Raster scale is fixed at 72 dpi, not a plan
option. `pagination = "may-change"` permits repagination but still protects text/URIs and
refuses ignored raster parameters. Booleans, NaN and infinities are invalid answers.

## Interpret differences

`FIDELITY001` reports page-count changes, `FIDELITY002` geometry changes and `FIDELITY003`
text changes. Missing URI targets are `FIDELITY004`; added targets are informational
`FIDELITY006`. URI actions compare as a multiset with standard reference resolution under
an established absolute catalog base. Query, fragment, encoding and duplicate targets remain
significant. Malformed/unestablished URI context is `FIDELITY008`; other comparison checks
continue. No target is fetched. Internal destinations, bookmarks, launch actions and hidden
references are outside this URI comparison.

Rendered pixels below `ink_threshold` are ink. Symmetric difference divided by
`max(source ink, candidate ink, 1)` is compared with tolerance (`FIDELITY005`); ratios can
exceed 1. Colour changes on the same threshold side are invisible. Difference images mark
changed ink in white and are declared evidence artifacts. Actual cropped/rounded bitmap
geometry is checked before allocation; a size mismatch is geometry, not a fabricated ratio.
Pages exceeding the existing 20-million-pixel limit produce `FIDELITY007`.

A skipped/incomplete raster check has no measured difference. Text extraction follows page
order, not semantic reading order. Compare within one machine/run; neither extraction, ink
nor URI equality establishes appearance, cross-machine identity or accessibility. Complete
the [human review](ACCESSIBILITY.md#human-acceptance).
