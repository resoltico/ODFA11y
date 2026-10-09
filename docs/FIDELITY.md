# Fidelity comparison

Remediation can look successful and still change links, wording or layout. `compare`
(and the `pipeline`) exports the source and the candidate with the same LibreOffice
executable and profile, then compares the two PDFs.

## What is compared

| Check | Rule | Applies |
| --- | --- | --- |
| Page count | `FID001` | `pagination = "same"` |
| Page sizes | `FID002` | `pagination = "same"` |
| Document text in reading order, whitespace-normalized | `FID003` | always |
| Source link targets present in the candidate | `FID004` | always |
| Links only in the candidate | `FID006` (info) | always |
| Rendered ink per page | `FID005` | `pagination = "same"` |
| Page too large to render safely | `FID007` | `pagination = "same"` |

Effective targets of URI actions on Link annotations are compared as a multiset,
independent of page. Absolute URIs are retained; relative references resolve against the
explicit catalog `/URI` `/Base`, following [RFC 3986 reference resolution](https://www.rfc-editor.org/rfc/rfc3986#section-5).
Relative targets require an absolute `http`, `https`, `ftp` or `file` Base; absent,
malformed or unsupported contexts cause a controlled execution failure. Query strings,
fragments, percent encoding and duplicate targets are retained. Targets are never fetched.
This scope excludes internal destinations, bookmarks, launch actions and hidden references;
it is not an inventory of every reference in a PDF. See the
[PDF Association's URI action guidance](https://pdfa.org/pdf-a-and-external-references/).

## Rendered ink

Each page is rendered with pdfium at `dpi` (default 72). A pixel is *ink* when its
luminance is below `ink_threshold` (default 200). A page differs by the fraction of its
ink that is present in only one render. Because the measure is relative to the page's
own ink, it is not diluted by white space:

| Change (measured on LibreOffice exports) | Difference |
| --- | --- |
| Metadata or identical content | 0 |
| Two hyperlinks added (colour and underline only) | about 3% |
| Links, alt text and header rows on a very small page | about 9% |
| Two spacer paragraphs removed, moving a line up | about 116% |

`raster_tolerance` (default `0.15`) sits between link-styling noise and real movement. A
page that fails writes `page-NNN-diff.png` (white marks ink present in one render only)
to `--diff-dir`, or to the evidence directory's `fidelity/`. Pages above 20 million
pixels at the chosen dpi are not rendered (`FID007`).

## Policy

```toml
[fidelity]
pagination = "same"        # or "may-change"
raster_tolerance = 0.15
ink_threshold = 200
dpi = 72
```

The public `FidelityPolicy` constructor and TOML loader use the same validation contract:
invalid choices raise `odfa11y.errors.ConfigError` before comparison/export/publication.
Pagination must be `same` or `may-change`, tolerance must be a finite non-negative number
(including values above 1.0), ink threshold an integer 0–255, and dpi a positive integer.
Booleans are not numeric policy values. NaN and either infinity are refused.

`"may-change"` is the explicit choice for operations that legitimately move content
(spacing normalization, spacer removal, header rows that repeat across pages): page
count, size and raster checks are skipped, while text and links stay gated. The effective
policy and the measured maximum difference are recorded in the report and the
[evidence](EVIDENCE.md), so a loosened gate is visible.

## Limits

Rendering is compared between two exports made on the same machine in one run; pixel
identity across machines is not claimed. A small movement in a dense page can stay under
the tolerance; lower `raster_tolerance` to tighten it. The comparison cannot judge
whether a change is *right*; see the human checks in
[Accessibility and limits](ACCESSIBILITY.md#human-acceptance).
