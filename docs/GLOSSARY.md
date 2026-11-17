# Glossary

## Terms

| Term | Meaning |
| --- | --- |
| answer | The explicit human instruction accepted by a decision kind. |
| batch file | A file listing independent document identifiers, sources and plans. |
| candidate | The in-memory or saved document produced by applying reviewed decisions. |
| decision | A registered kind, its reviewed target when needed, and a validated answer. |
| evidence bundle | The declared artifacts of a run with their integrity manifest. |
| fact | A typed measurement supplied by the check that owns it. |
| fidelity | Preservation of the source properties required by the reviewed policy. |
| finding | An observed document condition reported under an authoritative rule. |
| fingerprint | A short content identity that detects a target changing after review. |
| manifest (evidence) | The bundle version and hashes of its declared files. |
| plan | A source-bound set of human questions, answers and fidelity requirements. |
| profile | The selected level of assurance and acceptance strictness for a run. |
| publication | Making a completed artifact available at the chosen destination. |
| refusal | A policy or source condition that prevents the requested action safely. |
| remedy | A typed next action supplied by the producer of an expected failure. |
| rule | A registered condition with a stable identifier, severity and meaning. |
| source | The original document whose bytes bind the reviewed plan. |
| target | A canonical logical path paired with the fingerprint of reviewed content. |

## ExitStatus

| Value | Meaning |
| --- | --- |
| `0` | The requested checks completed without findings rejected by the selected policy. |
| `1` | Warnings prevent acceptance under the strict policy. |
| `2` | Errors or a document refusal prevent acceptance. |
| `3` | A tool or operating-system failure prevented completion. |
| `4` | The options, plan or output destination prevent the requested invocation. |

## Profile

| Value | Meaning |
| --- | --- |
| `source` | Inspect and remediate the OpenDocument source without native export. |
| `pdf` | Inspect source, native PDF export and fidelity without requiring veraPDF. |
| `production` | Require PDF/UA validation and reject warnings as well as errors. |

## Stage

| Value | Meaning |
| --- | --- |
| `audit-source` | Inspect accessibility conditions in the source document. |
| `remediate` | Apply the reviewed decisions under preservation guards. |
| `audit-remediated` | Inspect the candidate after applying reviewed decisions. |
| `export-source` | Export the captured source to PDF. |
| `export-remediated` | Export the remediation candidate to PDF. |
| `audit-pdf` | Inspect the exported PDF structure and content. |
| `validate-pdf` | Validate the exported PDF against PDF/UA with veraPDF. |
| `fidelity` | Compare the source and candidate exports under the fidelity policy. |
| `publish-evidence` | Publish the declared evidence artifacts and review record. |

## Step

| Value | Meaning |
| --- | --- |
| `prepare` | Validate inputs, capture source and resolve the required tools. |
| `audit-source` | Inspect accessibility conditions in the source document. |
| `remediate` | Apply the reviewed decisions under preservation guards. |
| `audit-remediated` | Inspect the candidate after applying reviewed decisions. |
| `export-source` | Export the captured source to PDF. |
| `export-remediated` | Export the remediation candidate to PDF. |
| `audit-pdf` | Inspect the exported PDF structure and content. |
| `validate-pdf` | Validate the exported PDF against PDF/UA with veraPDF. |
| `fidelity` | Compare the source and candidate exports under the fidelity policy. |
| `publish-evidence` | Publish the declared evidence artifacts and review record. |
| `audit-document` | Inspect one OpenDocument or PDF input. |
| `export-pdf` | Export an original document to PDF. |
| `export-candidate` | Render a candidate input for comparison. |
| `compare-fidelity` | Compare the original input artifacts for fidelity. |
| `probe-capabilities` | Measure a declared native capability with a synthetic document. |
| `batch-item` | Execute one identified batch item. |

## StepState

| Value | Meaning |
| --- | --- |
| `running` | The operation is in progress. |
| `passed` | The operation completed successfully. |
| `failed` | The operation failed or was interrupted. |
| `skipped` | The operation did not run. |

## ReviewTopic

| Value | Meaning |
| --- | --- |
| `alt-text` | Review whether graphic alternatives convey the intended meaning. |
| `chart-meaning` | Review whether chart descriptions explain the data and its significance. |
| `colour` | Review whether meaning depends solely on colour. |
| `colour-and-layout` | Review whether colour and placement communicate meaning accessibly. |
| `database-meaning` | Review whether database object descriptions explain their purpose. |
| `export-boundary` | Review the limits of native export assurance. |
| `header-cells` | Review whether header cells identify the intended data relationships. |
| `headings` | Review whether headings express the intended outline. |
| `hidden-content` | Review whether hidden content belongs in the accessible publication. |
| `image-meaning` | Review whether image descriptions explain their relevant content. |
| `labels-and-ranges` | Review whether sheet labels and ranges express the intended data relationships. |
| `language` | Review whether declared languages match the actual content. |
| `layers-and-annotations` | Review whether layers and annotations preserve meaningful content. |
| `layout` | Review whether placement and spacing preserve the intended reading flow. |
| `link-purpose` | Review whether link descriptions explain each destination or action. |
| `lists` | Review whether list structure expresses the intended grouping. |
| `mathematics` | Review whether spoken alternatives convey the mathematical expression. |
| `page-titles` | Review whether page titles identify their purpose. |
| `privacy-and-execution` | Review whether the publication contains private data or active content. |
| `reading-order` | Review whether the content follows the intended reading sequence. |
| `sheet-names` | Review whether worksheet names clearly identify their content. |
| `slides-and-notes` | Review whether slides and notes communicate their intended content. |
| `source-assurance` | Review the limits of source-only accessibility assurance. |
| `source-boundary` | Review the limits of the source inspection contract. |
| `table-headers` | Review whether table headers identify the intended row and column relationships. |

## Severity

| Value | Meaning |
| --- | --- |
| `error` | A finding prevents acceptance under every profile. |
| `warning` | A finding requires review and prevents strict acceptance. |
| `info` | An observation provides context without preventing acceptance. |

## RemedyAction

| Value | Meaning |
| --- | --- |
| `regenerate-plan` | Generate a fresh plan for the source and review its answers. |
| `rebind-plan` | Create a newly bound plan and review answers that no longer match. |
| `choose-output` | Choose an available output destination. |
| `install-tool` | Install or select the required native tool. |
| `edit-in-application` | Edit the named target in its authoring application. |
| `embed-resource` | Embed the named rendering resource in the source document. |

## ReportKind

| Value | Meaning |
| --- | --- |
| `odf` | Findings about the OpenDocument source. |
| `pdf` | Findings from built-in PDF inspection. |
| `pdf-validation` | Findings from independent PDF/UA validation. |
| `fidelity` | Findings about changes between source and candidate exports. |

## SkipReason

| Value | Meaning |
| --- | --- |
| `missing-input` | A preceding stage did not produce an input this stage requires. |
| `profile` | The selected profile does not require this stage. |

## DecisionScope

| Value | Meaning |
| --- | --- |
| `document` | The answer applies to the whole source bound by the plan digest. |
| `target` | The answer describes a specific content target bound by a fingerprint. |

## Family

| Value | Meaning |
| --- | --- |
| `text` | A text document expresses prose and its structure. |
| `spreadsheet` | A spreadsheet expresses cells, formulas and tabular relationships. |
| `presentation` | A presentation expresses slides and their associated notes. |
| `drawing` | A drawing expresses objects placed on pages. |
| `formula` | A formula document expresses a mathematical expression. |
| `chart` | A chart document expresses data graphically. |
| `image` | An image document expresses graphic content. |
| `database` | A database document describes forms, reports, queries and data sources. |

## Layout

| Value | Meaning |
| --- | --- |
| `package` | An OpenDocument ZIP package with separate members. |
| `flat` | A single XML document containing the OpenDocument parts. |

## Part

| Value | Meaning |
| --- | --- |
| `content` | The logical document body contains the authored content. |
| `styles` | The logical style part defines shared and master styles. |
| `meta` | The logical metadata part describes the document. |
| `settings` | The logical settings part holds application settings. |
| `manifest` | The package manifest declares stored members and their media types. |

## Use

| Value | Meaning |
| --- | --- |
| `audit` | Inspect the source without changing it. |
| `plan` | Prepare source-bound questions for human decisions. |
| `remediate` | Apply explicitly reviewed source edits. |
| `export` | Send a source with established rendering dependencies to its native exporter. |
| `style` | Inspect style declarations and usage without changing the source. |

## ProbeId

| Value | Meaning |
| --- | --- |
| `link-descriptions` | Measure whether accessible link descriptions survive export. |
| `decorative-graphic-role` | Measure whether decorative graphics retain their nonsemantic role. |
| `writer-header-columns` | Measure whether Writer column headers survive PDF export. |
| `math-tagging` | Measure whether exported mathematics has usable tagged structure. |
| `calc-pdfua` | Measure whether a semantic Calc table passes PDF inspection and PDF/UA validation. |

## CapabilityStatus

| Value | Meaning |
| --- | --- |
| `supported` | The declared synthetic experiment established the capability. |
| `unsupported` | The declared synthetic experiment did not establish the capability. |
| `not-tested` | The capability was not measured conclusively. |

## TableKind

| Value | Meaning |
| --- | --- |
| `data` | The table has explicit evidence of data-table intent. |
| `complex-data` | The data table has relationships requiring explicit human review. |
| `layout-candidate` | The table may position content instead of expressing data relationships. |
| `ambiguous` | The table has insufficient evidence to infer data or layout intent. |

## Status

| Value | Meaning |
| --- | --- |
| `applied` | The edit changed XML and established its postcondition. |
| `unchanged` | The intended postcondition already held without changing XML. |
| `failed` | The edit could not establish its required postcondition. |

## ViolationKind

| Value | Meaning |
| --- | --- |
| `failed-outcome` | An edit did not establish its required postcondition. |
| `protected-content` | An edit changed content outside the allowed preservation contract. |
| `opaque-resource` | An edit changed a payload that must remain opaque. |
| `schema-regression` | An edit introduced an OpenDocument schema violation. |
| `edit-accounting` | An edit report disagrees with the observed XML changes. |
| `foreign-operation` | An edit is unsupported by the selected document family. |
