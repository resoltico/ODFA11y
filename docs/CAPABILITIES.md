# Measured native capabilities

Recorded with ODFA11y 0.8.0 on `macOS-27.0.1-arm64-arm-64bit-Mach-O`.
LibreOffice 26.8.1.1; veraPDF 1.30.3.
[Doctor record](measurements/doctor.json) is the measurement authority.

| Probe | Family | Result |
| --- | --- | --- |
| `link-descriptions` | text | unsupported |
| `decorative-graphic-role` | text | unsupported |
| `writer-header-columns` | text | unsupported |
| `math-tagging` | formula | unsupported |
| `calc-pdfua` | spreadsheet | unsupported |

These verdicts apply to each probe's authored input and exporter identity.
Unsupported results do not waive document-level PDF gates. Execution failures are
reported separately and retried; only conclusive observations are batch-cached.
Doctor measures every probe; pipelines select relevant family/decision probes.

The [text-structure measurements](measurements/text-exports.json) additionally
record fixture-specific roles and independent validator outcomes. Read the
[accessibility boundaries](ACCESSIBILITY.md) before interpreting a machine pass.
