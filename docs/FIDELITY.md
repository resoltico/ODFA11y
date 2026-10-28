# Fidelity comparison

`compare` and pipeline fidelity compare the source and candidate PDFs. ODF inputs are
exported with the same LibreOffice executable/profile in one run; PDF inputs are read
directly. This detects protected publication changes, not accessibility or correct meaning.

## What is compared

| Check | Rule | Applies |
| --- | --- | --- |
| Page count | `FID001` | `pagination = "same"` |
| Page sizes | `FID002` | `pagination = "same"` |
| Extracted page text, whitespace-normalized | `FID003` | Always |
| Source URI link targets present in candidate | `FID004` | Always |
| Additional candidate URI link targets | `FID006` (info) | Always |
| Rendered ink per page | `FID005` | `pagination = "same"`, with equal page counts/sizes |
| Page too large to render safely | `FID007` | When raster comparison runs |

Text comes from PDF page extraction in page order, not structure-tree reading order.
Logical reading order and assistive-technology behavior require separate review.

URI actions on Link annotations compare as a multiset independent of page. Absolute URIs
are retained; relative references resolve against catalog `/URI` `/Base` under
[RFC 3986](https://www.rfc-editor.org/rfc/rfc3986#section-5). A relative reference requires
an absolute `http`, `https`, `ftp` or `file` base; absent/malformed/unsupported contexts fail
execution. Query strings, fragments, percent encoding and duplicate targets remain.
Components must satisfy the RFC grammar, including numeric ports and correctly placed IP
literal brackets/delimiters. No target is fetched.

Internal destinations/bookmarks, launch actions and hidden references are outside this
link comparison. It is not an inventory of every PDF reference; see the
[PDF Association URI guidance](https://pdfa.org/pdf-a-and-external-references/).

## Rendered ink

pdfium renders each page at `dpi` (default 72). A pixel is ink if luminance is below
`ink_threshold` (default 200). The difference is the number of pixels inked in exactly
one render divided by `max(source ink pixels, candidate ink pixels, 1)`. It is relative
to ink, not white page area, and can exceed 1. Pure colour changes that stay on the same
side of the threshold are invisible to this binary measure.

A ratio above `raster_tolerance` (default `0.15`) produces `FID005`. When a diff directory
is supplied, `page-NNN-diff.png` marks differing ink in white; pipeline uses `fidelity/`.
More than 20 million pixels at the chosen DPI produces `FID007` instead of rendering.
DPI beyond floating-point numeric range fails with `ToolFailedError` before conversion;
representable DPI remains subject to the pixel budget.

## Policy

```toml
[fidelity]
pagination = "same"        # or "may-change"
raster_tolerance = 0.15
ink_threshold = 200
dpi = 72
```

`FidelityPolicy` and TOML use the same validation: pagination is `same`/`may-change`,
tolerance finite/non-negative (no upper cap), threshold an integer 0–255, DPI a positive
integer. Booleans are not numeric values; NaN/infinities refuse. Invalid choices raise
`odfa11y.errors.PlanError` before comparison/export/publication.

`may-change` permits deliberate repagination, spacing or repeated-header movement by
skipping page-count/size/raster checks. Extracted text and links remain gated. Review
layout manually. The effective policy and available raster measurements are recorded in
the report and [evidence](EVIDENCE.md); skipped raster checks provide no measured difference.

## Limits

Renders compare on one machine/run; cross-machine pixel identity is not claimed. Movement
can remain below tolerance; lowering it tightens the threshold without establishing correct
layout. Text extraction, binary ink and URI matching have distinct blind spots. Review the
publication using the [human checklist](ACCESSIBILITY.md#human-acceptance).
