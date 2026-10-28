# Fidelity comparison

Compare the original and candidate independently of accessibility checks:

```sh
odfa11y compare original.odt reviewed.odt --diff-dir differences --plan reviewed.toml
```

ODF inputs use the same LibreOffice executable/profile within a run; PDF inputs are read
directly. Text and URI targets always gate. With `pagination = "same"`, page counts,
page sizes and rendered ink also gate. Text extraction follows page order, not logical
structure reading order. The [human checklist](ACCESSIBILITY.md#human-acceptance) remains necessary.

## Set the policy

```toml
[fidelity]
pagination = "same"        # or "may-change"
raster_tolerance = 0.15
ink_threshold = 200
dpi = 72
```

Choose `may-change` only after reviewing intended repagination/spacing: it skips page-count,
size and raster checks, while preserving text/URI gates. The typed `FidelityPolicy` and
TOML share validation. Tolerance is finite/non-negative, threshold is integer 0–255 and
DPI is a positive integer; booleans, NaN and infinities refuse before export/publication.

## Interpret differences

`FID001`/`FID002` identify page count/size changes, `FID003` text changes and `FID004`
missing URI targets. Added targets are informational `FID006`. URI actions compare as a
multiset; relative references require a valid absolute catalog URI base. Grammar, query,
fragment, percent encoding and duplicate targets remain significant; no target is fetched.
Internal destinations, bookmarks, launch actions and hidden references are outside this comparison.

pdfium classifies pixels below `ink_threshold` as ink. The symmetric difference divided
by `max(source ink, candidate ink, 1)` is compared with tolerance (`FID005`); the ratio can
exceed 1. Pure colour changes on the same threshold side are invisible. Diff images mark
changed ink in white. Pages exceeding 20 million pixels produce `FID007`; unrepresentable
DPI fails before conversion. See [PDF limits](ACCESSIBILITY.md#threat-model).

Measurements and skipped checks are recorded in [evidence](EVIDENCE.md). A skipped raster
check supplies no measured difference. Compare within one machine/run; neither extraction,
binary ink nor URI preservation establishes intended appearance or cross-machine identity.
