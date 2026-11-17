# Native capability probes

Run `odfa11y doctor --format json` to measure the installed tools and retain their
identities, observed capabilities and reasons for unmeasured results.

| Probe | Family | Meaning | Related rules | Requires veraPDF |
| --- | --- | --- | --- | --- |
| `link-descriptions` | text | Measure whether accessible link descriptions survive export. | `LINK003` | no |
| `decorative-graphic-role` | text | Measure whether decorative graphics retain their nonsemantic role. | `GRAPHIC001`, `GRAPHIC003` | no |
| `writer-header-columns` | text | Measure whether Writer column headers survive PDF export. | `TABLE003` | no |
| `math-tagging` | formula | Measure whether exported mathematics has usable tagged structure. | `MATH003`, `PDF004` | no |
| `calc-pdfua` | spreadsheet | Measure whether a semantic Calc table passes PDF inspection and PDF/UA validation. | `TABLE004`, `PDFUA001` | yes |

A verdict applies to that probe's authored input, tool identity and environment.
It does not establish behavior for every document or platform. Unsupported results
never waive document-level PDF gates. Execution failures remain separate from
supported/unsupported observations; unavailable prerequisites leave explicit
not-tested results. Runs and batches do not conduct these experiments.

Complete the [document workflow](WORKFLOW.md) and
[human acceptance checks](ACCESSIBILITY.md#human-acceptance) for the actual publication.
