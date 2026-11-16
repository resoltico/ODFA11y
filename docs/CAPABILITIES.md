# Measured native capabilities

Recorded with ODFA11y 0.8.0 on `macOS-27.2.1-arm64-arm-64bit-Mach-O`.
LibreOffice 26.8.3.1; veraPDF unavailable.
[Doctor record](measurements/doctor.json) is the measurement authority.

| Probe | Meaning | Rules | Result | Reason |
| --- | --- | --- | --- | --- |
| `link-descriptions` | Measure whether accessible link descriptions survive export. | `LINK003` | unsupported | — |
| `decorative-graphic-role` | Measure whether decorative graphics retain their nonsemantic role. | `GRAPHIC001`, `GRAPHIC003` | unsupported | — |
| `writer-header-columns` | Measure whether Writer column headers survive PDF export. | `TABLE003` | unsupported | — |
| `math-tagging` | Measure whether exported mathematics has usable tagged structure. | `MATH003`, `PDF004` | unsupported | — |
| `calc-pdfua` | Measure whether a semantic Calc table passes PDF inspection and PDF/UA validation. | `TABLE004`, `PDFUA001` | not-tested | veraPDF unavailable |

These verdicts apply to each probe's authored input and exporter identity.
Unsupported results do not waive document-level PDF gates. Execution failures are
reported separately. Doctor measures applicable experiments; an unavailable required
tool leaves a probe unmeasured with its reason. Runs and batches never conduct probes.

The [text-structure measurements](measurements/text-exports.json) additionally
record fixture-specific roles and independent validator outcomes. Read the
[accessibility boundaries](ACCESSIBILITY.md) before interpreting a machine pass.
