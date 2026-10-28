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

Audit ODF or PDF files without changing them.

| Argument | Values | Required | Default / choices | Help |
| --- | --- | --- | --- | --- |
| `-h, --help` | 0 | no |  | show this help message and exit |
| `sources` | + | yes |  |  |
| `--schema` | 0 | no | False | Validate ODF files against the ODF schema. |
| `--verapdf` | 0 | no | False | Validate PDF files with veraPDF (PDF/UA-1). |
| `--verapdf-path` | 1 | no |  | veraPDF executable (implies --verapdf); default: PATH. |
| `--timeout` | 1 | no | 120 | Native tool timeout in seconds (default: 120). |
| `--format` | 1 | no | text; choices: text, json, sarif |  |
| `--source-root` | 1 | no |  | Confined source root, required for SARIF. |
| `--strict` | 0 | no | False | Fail on warnings too. |

## plan

Print a source-bound plan of disabled human answers.

| Argument | Values | Required | Default / choices | Help |
| --- | --- | --- | --- | --- |
| `-h, --help` | 0 | no |  | show this help message and exit |
| `source` | 1 | yes |  |  |

## remediate

Apply reviewed decisions to a separate ODF document.

| Argument | Values | Required | Default / choices | Help |
| --- | --- | --- | --- | --- |
| `-h, --help` | 0 | no |  | show this help message and exit |
| `source` | 1 | yes |  |  |
| `destination` | 1 | yes |  |  |
| `--plan` | 1 | yes |  | Source-bound TOML plan. |
| `--rebind` | 0 | no | False | Explicitly accept a different source digest; target fingerprints still apply. |
| `--dry-run` | 0 | no | False | Report outcomes without writing. |
| `--format` | 1 | no | text; choices: text, json |  |

## export

Export an ODF document to PDF/UA with LibreOffice.

| Argument | Values | Required | Default / choices | Help |
| --- | --- | --- | --- | --- |
| `-h, --help` | 0 | no |  | show this help message and exit |
| `source` | 1 | yes |  |  |
| `destination` | 1 | yes |  |  |
| `--soffice` | 1 | no |  | LibreOffice executable. |
| `--timeout` | 1 | no | 120 | Native tool timeout in seconds (default: 120). |

## compare

Compare two ODF or PDF files for fidelity.

| Argument | Values | Required | Default / choices | Help |
| --- | --- | --- | --- | --- |
| `-h, --help` | 0 | no |  | show this help message and exit |
| `source` | 1 | yes |  |  |
| `candidate` | 1 | yes |  |  |
| `--plan` | 1 | no |  | TOML file whose [fidelity] table sets the policy. |
| `--diff-dir` | 1 | no |  | Write images of pages that differ here. |
| `--soffice` | 1 | no |  | LibreOffice executable. |
| `--timeout` | 1 | no | 120 | Native tool timeout in seconds (default: 120). |
| `--format` | 1 | no | text; choices: text, json, sarif |  |
| `--source-root` | 1 | no |  | Confined source root, required for SARIF. |
| `--strict` | 0 | no | False | Fail on warnings too. |

## pipeline

Remediate, export, validate, compare and keep evidence.

| Argument | Values | Required | Default / choices | Help |
| --- | --- | --- | --- | --- |
| `-h, --help` | 0 | no |  | show this help message and exit |
| `source` | 1 | yes |  |  |
| `--plan` | 1 | yes |  | Source-bound TOML plan. |
| `--output-dir` | 1 | yes |  | Evidence directory to create. |
| `--profile` | 1 | no | verify; choices: source, verify, production | Assurance profile (default: verify): source checks source/remediation; verify adds PDF diagnostics and fidelity; production also requires veraPDF and gates warnings. |
| `--verapdf-path` | 1 | no |  | veraPDF executable for the production profile. |
| `--soffice` | 1 | no |  | LibreOffice executable. |
| `--timeout` | 1 | no | 120 | Native tool timeout in seconds (default: 120). |
| `--format` | 1 | no | text; choices: text, json |  |
| `--rebind` | 0 | no | False | Explicitly rebind this plan to the selected source. |

## batch

Run independent manifest items and retain aggregate evidence.

| Argument | Values | Required | Default / choices | Help |
| --- | --- | --- | --- | --- |
| `-h, --help` | 0 | no |  | show this help message and exit |
| `--rebind` | 0 | no | False | Explicitly rebind each plan to its selected source. |
| `manifest` | 1 | yes |  |  |
| `--output-dir` | 1 | yes |  |  |
| `--profile` | 1 | no | verify; choices: source, verify, production | Assurance profile (default: verify): source checks source/remediation; verify adds PDF diagnostics and fidelity; production also requires veraPDF and gates warnings. |
| `--verapdf-path` | 1 | no |  |  |
| `--soffice` | 1 | no |  | LibreOffice executable. |
| `--timeout` | 1 | no | 120 | Native tool timeout in seconds (default: 120). |
| `--format` | 1 | no | text; choices: text, json |  |

## verify

Verify an evidence directory against its manifest.

| Argument | Values | Required | Default / choices | Help |
| --- | --- | --- | --- | --- |
| `-h, --help` | 0 | no |  | show this help message and exit |
| `directory` | 1 | yes |  |  |

## doctor

Show tool and dependency versions and what the PDF export supports.

| Argument | Values | Required | Default / choices | Help |
| --- | --- | --- | --- | --- |
| `-h, --help` | 0 | no |  | show this help message and exit |
| `--soffice` | 1 | no |  | LibreOffice executable. |
| `--timeout` | 1 | no | 120 | Native tool timeout in seconds (default: 120). |
| `--verapdf-path` | 1 | no |  | Selected veraPDF executable. |
| `--format` | 1 | no | text; choices: text, json |  |

## Exit statuses

| Code | Outcome |
| --- | --- |
| 0 | Passed |
| 1 | Strict Warnings |
| 2 | Errors |
| 3 | Execution Failure |
| 4 | Usage Error |

Aggregation precedence: **3 > 4 > 2 > 1 > 0**.

A passing dry run can have `published=false`; a refused candidate exits 2.
Execution errors retain status 3; invalid arguments/plans use 4.
