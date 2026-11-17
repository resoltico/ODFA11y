# Command reference

Generated from the CLI parser and core outcome vocabulary.
Use `odfa11y COMMAND --help` for executable examples.
Values: 0 means a flag, 1 one value, + one or more, ? optional, * zero or more.

## Global options

| Argument | Values | Required | Default / choices | Help |
| --- | --- | --- | --- | --- |
| `-h, --help` | 0 | no |  | show this help message and exit |
| `--version` | 0 | no |  | show program's version number and exit |

## audit

Inspect ODF or PDF inputs without changing them.

| Argument | Values | Required | Default / choices | Help |
| --- | --- | --- | --- | --- |
| `-h, --help` | 0 | no |  | show this help message and exit |
| `sources` | + | yes |  | One or more input documents. |
| `--schema` | 0 | no | False | Validate ODF against its declared schema. |
| `--validate` | 0 | no | False | Request independent PDF/UA validation. |
| `--verapdf` | 1 | no |  | veraPDF executable (default: PATH). |
| `--timeout` | 1 | no | 120.0 | Seconds per native call (default: 120). |
| `--format` | 1 | no | text; choices: text, json, sarif | Output representation (default: text). |
| `--strict` | 0 | no | False | Reject warning findings as well as errors. |
| `--source-root` | 1 | no |  | Confined source root, required for SARIF output. |

## plan

Prepare source-bound questions with inert unanswered blocks.

| Argument | Values | Required | Default / choices | Help |
| --- | --- | --- | --- | --- |
| `-h, --help` | 0 | no |  | show this help message and exit |
| `source` | 1 | yes |  | Input document. |
| `--from` | 1 | no |  | Carry answers whose bindings still match. |
| `--all` | 0 | no | False | Include optional overrides not raised by findings. |
| `--format` | 1 | no | text; choices: text, json | Output representation (default: text). |

## remediate

Apply reviewed answers under preservation and schema guards.

| Argument | Values | Required | Default / choices | Help |
| --- | --- | --- | --- | --- |
| `-h, --help` | 0 | no |  | show this help message and exit |
| `source` | 1 | yes |  | Input document. |
| `destination` | 1 | yes |  | Output file, distinct from the source. |
| `--plan` | 1 | yes |  | TOML plan with reviewed answers and a fidelity policy. |
| `--dry-run` | 0 | no | False | Preview changes and remaining findings without publishing. |
| `--replace` | 0 | no | False | Atomically replace an existing regular output file. |
| `--format` | 1 | no | text; choices: text, json | Output representation (default: text). |

## export

Publish a guarded native PDF export.

| Argument | Values | Required | Default / choices | Help |
| --- | --- | --- | --- | --- |
| `-h, --help` | 0 | no |  | show this help message and exit |
| `source` | 1 | yes |  | Input document. |
| `destination` | 1 | yes |  | Output file, distinct from the source. |
| `--soffice` | 1 | no |  | LibreOffice executable (default: PATH). |
| `--timeout` | 1 | no | 120.0 | Seconds per native call (default: 120). |
| `--replace` | 0 | no | False | Atomically replace an existing regular output file. |
| `--format` | 1 | no | text; choices: text, json | Output representation (default: text). |

## compare

Compare source and candidate fidelity under an explicit policy.

| Argument | Values | Required | Default / choices | Help |
| --- | --- | --- | --- | --- |
| `-h, --help` | 0 | no |  | show this help message and exit |
| `source` | 1 | yes |  | Input document. |
| `candidate` | 1 | yes |  | Candidate document to compare with the source. |
| `--plan` | 1 | no |  | TOML plan with reviewed answers and a fidelity policy. |
| `--diff-dir` | 1 | no |  | Directory for declared difference images. |
| `--soffice` | 1 | no |  | LibreOffice executable (default: PATH). |
| `--timeout` | 1 | no | 120.0 | Seconds per native call (default: 120). |
| `--format` | 1 | no | text; choices: text, json, sarif | Output representation (default: text). |
| `--strict` | 0 | no | False | Reject warning findings as well as errors. |
| `--source-root` | 1 | no |  | Confined source root, required for SARIF output. |

## run

Prepare, remediate and retain selected assurance evidence.

| Argument | Values | Required | Default / choices | Help |
| --- | --- | --- | --- | --- |
| `-h, --help` | 0 | no |  | show this help message and exit |
| `source` | 1 | yes |  | Input document. |
| `--plan` | 1 | yes |  | TOML plan with reviewed answers and a fidelity policy. |
| `--output-dir` | 1 | yes |  | Evidence output directory. |
| `--profile` | 1 | no | pdf; choices: source, pdf, production | Assurance profile (default: pdf): source: Inspect and remediate the OpenDocument source without native export.; pdf: Inspect source, native PDF export and fidelity without requiring veraPDF.; production: Require PDF/UA validation and reject warnings as well as errors. |
| `--soffice` | 1 | no |  | LibreOffice executable (default: PATH). |
| `--timeout` | 1 | no | 120.0 | Seconds per native call (default: 120). |
| `--verapdf` | 1 | no |  | veraPDF executable (default: PATH). |
| `--format` | 1 | no | text; choices: text, json | Output representation (default: text). |

## batch

Execute independent batch-file items and retain progress.

| Argument | Values | Required | Default / choices | Help |
| --- | --- | --- | --- | --- |
| `-h, --help` | 0 | no |  | show this help message and exit |
| `batch_file` | 1 | yes |  | Batch file listing document IDs, source paths and plans. |
| `--output-dir` | 1 | yes |  | Evidence output directory. |
| `--profile` | 1 | no | pdf; choices: source, pdf, production | Assurance profile (default: pdf): source: Inspect and remediate the OpenDocument source without native export.; pdf: Inspect source, native PDF export and fidelity without requiring veraPDF.; production: Require PDF/UA validation and reject warnings as well as errors. |
| `--soffice` | 1 | no |  | LibreOffice executable (default: PATH). |
| `--timeout` | 1 | no | 120.0 | Seconds per native call (default: 120). |
| `--verapdf` | 1 | no |  | veraPDF executable (default: PATH). |
| `--format` | 1 | no | text; choices: text, json | Output representation (default: text). |

## verify-evidence

Check recorded-file integrity without asserting accessibility.

| Argument | Values | Required | Default / choices | Help |
| --- | --- | --- | --- | --- |
| `-h, --help` | 0 | no |  | show this help message and exit |
| `directory` | 1 | yes |  | Evidence bundle directory to verify. |
| `--format` | 1 | no | text; choices: text, json | Output representation (default: text). |

## doctor

Measure native tool identities and scoped capability experiments.

| Argument | Values | Required | Default / choices | Help |
| --- | --- | --- | --- | --- |
| `-h, --help` | 0 | no |  | show this help message and exit |
| `--soffice` | 1 | no |  | LibreOffice executable (default: PATH). |
| `--timeout` | 1 | no | 120.0 | Seconds per native call (default: 120). |
| `--verapdf` | 1 | no |  | veraPDF executable (default: PATH). |
| `--format` | 1 | no | text; choices: text, json | Output representation (default: text). |

## Exit statuses

| Code | Outcome |
| --- | --- |
| 0 | Passed |
| 1 | Strict Warnings |
| 2 | Errors |
| 3 | Execution Failure |
| 4 | Usage Error |

Aggregation precedence: **3 > 4 > 2 > 1 > 0**.

A passing dry run can have `publication="preview"`; a refused candidate exits 2.
Execution errors retain status 3; invalid arguments/plans use 4.
