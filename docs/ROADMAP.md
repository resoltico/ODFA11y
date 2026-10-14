# Roadmap to v1.0.0

ODFA11y helps people inspect OpenDocument sources, make explicit accessibility decisions,
and verify the resulting publications. The route to v1.0.0 prioritizes trustworthy source
semantics and preservation, then deeper document understanding, then a complete review
workflow. A clean automated report remains evidence about selected checks, never an
accessibility certificate.

This is the current release plan. GitHub issues and pull requests track its execution.
The [document family design](DOCUMENT_FAMILIES_AND_WORKFLOWS.md) records work shipped in
v0.5.0; it is not an outstanding backlog. v0.6.0 is the published baseline for this plan.
The core API and CLI changes from the reviewed `main` baseline are included in the
0.7.0 candidate together with the source/preservation foundation work below. Publication
remains pending and separately authorized.

Milestones have completion criteria rather than promised dates. Each feature includes its
library and CLI behavior, configuration, audit findings, preservation, native application
evidence where applicable, documentation and distribution contents. A discovered defect
in a supported safety or correctness contract is repaired in the current milestone;
later milestones are product expansion, not a place to park foundational defects.

## Standards and design boundaries

Use the final OASIS Standard editions of [ODF 1.4](https://docs.oasis-open.org/office/OpenDocument/v1.4/os/)
and the bundled ODF 1.3 schemas for the supported source versions. The four ODF parts
cover introduction, packages, document markup and OpenFormula. Format validity,
source accessibility, exporter capability, PDF/UA validation and human review are separate
properties. ODF 1.4 features must not be inserted into an ODF 1.3 document silently.

Keep the existing parsed document model, family adapters, shared ODF vocabulary and
generic workflow. Strengthen a boundary where evidence exposes a weakness; replace a
mechanism when that reduces total complexity. Do not introduce a universal document
model, a plugin framework, a formula evaluator or a PDF repair engine to meet this plan.
Existing configuration and APIs can break before v1.0 when a reviewed change warrants it;
update every consumer and explain the user action without aliases or migration shims.

OpenDocument remains the product scope through v1.0. DOCX is a possible v2 discussion,
not a committed feature or a reason to generalize the ODF architecture now.

## v0.7.0 Source semantics and preservation foundations

The release combines the implemented public core API and CLI work with the following
source and publication assurance changes. Complete all of them before release.

| Work | Required outcome |
| --- | --- |
| Text contexts and preservation | Distinguish current body content from change history, annotations, notes and text boxes. Historical headings must not determine the live outline, remediation must not rewrite deleted history, and explicit spaces/tabs/breaks must retain word boundaries. Correct blanket merged-cell errors to review warnings while retaining broken-grid errors and strict gates. Protect existing references, graphic geometry and payloads as well as words; negative controls must demonstrate rejection of silent damage. |
| Protected packages | Identify declared signatures and manifest encryption before semantic parsing. Read-only signature inspection states that cryptographic validity was not checked. Refuse remediation of signed packages, including dry runs and empty plans. Refuse incomplete inspection, remediation and guarded export of encrypted packages; no decryption, stripping or signing feature is implied. |
| Language defaults | Preserve well-formed BCP 47 tags, including scripts, numeric regions, variants and extensions. Read and write the standard split or full-tag representation correctly, replace conflicting defaults, and set all three default script channels while preserving explicit content overrides. |
| Decorative graphics | Add explicit meaningful versus decorative decisions using ODF 1.4 graphic style semantics. Resolve inheritance, derive styles per reviewed target, and keep unrelated objects unchanged. Update every family that audits these graphics. A decorative declaration must never hide broken payloads or prove PDF artifact behavior. |
| Link descriptions | Audit source link purpose and author supplied `office:title` descriptions through family operations for text, spreadsheet, presentation and drawing links. Preserve visible labels, destinations and target names. Keep exporter-specific Name requirements separate. |
| Formula resource context | Classify declared OpenFormula resource and filename dependencies without evaluating formulas. Guard native export and captured identity consistently, distinguish navigation from external data access, and refuse unestablished formula constructs explicitly. |
| Native execution limits | Validate finite positive portable timeouts before work starts and apply the selected work timeout to LibreOffice and veraPDF. Document separately bounded identity probes and process cleanup limits. |
| Public contracts | Document the supported library entrypoints, incremental audit results, errors, observers, output ownership and low-level caller responsibilities. Keep CLI and library policy equivalent; correct rule-remedy and preservation documentation drift. State the stable-directory prerequisite for evidence verification truthfully. |
| Release assurance | Verify the source archive's contributor materials and development flow outside the checkout. Fail closed when release-tag or release-state queries are uncertain. Verify draft identity and exact tested assets, and document correction of unpublished drafts. |

The implementing agent must complete a focused design challenge before building the
affected mechanisms and revisit it when a real native experiment contradicts an assumption.
The 0.7.0 candidate implements these work units. Local verification on 2026-10-14 passed
1,862 unit tests and all 67 required real LibreOffice/veraPDF integration cases, without
native skips. The candidate's distribution and delivered-commit hosted checks are recorded
with its review result; they must pass before publication.

Measured LibreOffice 26.8.1.1 still ignores standard decorative roles and `office:title`
PDF descriptions, and aliases/drops some language tags. Source declarations are retained;
strict PDF/veraPDF failures remain visible. Mixed graphic/presentation precedence and other
unestablished style/formula states refuse explicitly. These native conditions are not
postponed implementation repairs or claims of PDF accessibility. Human review and separately
authorized rollout remain required.

Acceptance requires package and flat-layout tests, wrong-type and stale-target rejection,
idempotence, preservation controls and real native positive and negative cases. Required
policy, lint, format, type, boundary, coverage, distribution and security checks pass, with
real LibreOffice and veraPDF integration on Linux, macOS and Windows. The hosted checks
must validate the release commit and tested assets. Preserve known exporter failures as
explicit outcomes; do not suppress them to make this release green.

## v0.8.0 Text structure and navigation

Build on the context and preservation contracts completed in v0.7.0 to make text audits
useful for longer, multilingual and structurally complex documents.

- Audit actual list structure, continuation identities, nested lists and manually simulated
  list candidates. Separate a structural defect from an author's decision about intended
  list meaning. Do not infer a list rewrite from typography.
- Expand hyperlink and internal-reference integrity checks beyond the descriptions added
  in v0.7. Treat LibreOffice's `office:name` requirement as an exporter constraint: ODF
  defines it as a target name, not the generic accessible description. Do not repurpose
  names or break incoming references.
- Check bookmarks, cross-references, note anchors and note bodies for missing or ambiguous
  relationships, using separate reading contexts. Add native fixtures for multi-column
  text, floating frames, sections and notes; report reading-order uncertainty explicitly.
- Resolve effective language for paragraph and inline content through named, automatic and
  direct styles, including script channels. Offer explicit language overrides bound to
  reviewed targets; preserve authored overrides and text.
- Distinguish data tables, layout candidates and valid complex grids. Audit available
  header relationships and missing information without equating every merged cell with
  an accessibility failure. Keep ambiguous or unsupported remediation as an explicit
  refusal, with actionable native editing guidance.
- Expose tracked, hidden and conditional content as review contexts. Preserve it and make
  uncertainty visible; accepting or rejecting revisions is not an implicit remediation.

Completion requires native documents combining these structures, not only isolated XML
fixtures. The source audit, editable decisions, PDF structure results and reading-order
review must agree about their scope. New location or serialized contracts receive an
explicit format change where required. Existing v0.7 safeguards remain regression gates.

## v0.9.0 Data documents and review completion

Extend useful assistance across the already recognized families and close the gap between
automated evidence and an accountable human review.

- Add explicit spreadsheet header decisions where standard markup and Calc behavior can
  be established. Separate print repetition from actual header relationships; keep cell
  values, formulas, references, merges and hidden state protected. Broaden chart audits
  and expose cached-data and external-provider limits without recalculation or fetching.
- Audit form labels, label-to-control references, keyboard order and grouping in supported
  document families. Offer supplied label/description decisions only where native reload
  proves the standard semantics. Never execute submissions, scripts, SQL or connections.
- Inspect embedded chart and MathML accessibility at a bounded declared boundary, with
  origin locations and explicit unsupported internals. Keep standalone Math, Chart, Image
  and Base source assurance distinct from any measured PDF export capability.
- Add a review record bound to the source, plan and final artifact digests, with explicit
  human decisions, unresolved items and invalidation after relevant changes. Reuse the
  evidence identity and review-item sources; do not create a second remediation plan or
  claim that a reviewer checkbox is an accessibility certificate.
- Expand the corpus to independently authored ODF producers and documented screen-reader
  and keyboard review of representative publications. Publish measured capabilities by
  family, producer and exporter version. Unsupported runtime combinations remain explicit.

Completion requires an end-to-end reviewed example for text, spreadsheet and presentation
or drawing, plus honest source-only examples for families without qualified PDF export.
Positive and negative controls must prove review invalidation and preservation. A native
exporter limitation may remain only as a precise supported boundary with user guidance;
repair an upstream capability when demonstrated rather than introducing hidden conversion
or PDF mutation.

## v1.0.0 Stable supported contracts

v1.0.0 is the first stable contract for the documented supported workflows. It does not
promise automatic accessibility, every ODF feature, every producer or a conforming PDF
from every family.

- Freeze and publish the supported library imports, CLI behavior, TOML schema, finding and
  logical-location contracts, report/evidence formats and exit meanings. Remove obsolete
  public surfaces before the freeze and define the subsequent compatibility policy.
- Complete the standards-to-capability review: every accessibility-relevant feature group
  considered in the roadmap has an implemented check, an explicit manual review step or a
  stated unsupported boundary. Keep this account tied to code, fixtures and test results;
  do not maintain an unverified claim inventory.
- Qualify the supported tool and operating-system matrix using real applications and
  representative authored documents. Publish native limitations, human acceptance results
  and the exact release artifacts to which the claims apply.
- Demonstrate clean installation and the shortest documented workflow from both wheel and
  source archive, with actionable errors for missing tools and unsupported inputs.
- Resolve release-blocking correctness and security findings, complete independent design
  and implementation review, and publish reproducible artifacts with provenance and a
  changelog that states breaking actions and material limits.

Keep v1.0.0 unreleased until those criteria are satisfied. Work added later must respect
the stable supported contracts; speculative platform expansion does not delay this scope.

## Standards references for implementation

These sources guide feature semantics; they do not establish application behavior.

- [ODF 1.4 Part 2](https://docs.oasis-open.org/office/OpenDocument/v1.4/os/part2-packages/OpenDocument-v1.4-os-part2-packages.html): package protection, signatures, metadata and package IRIs.
- [ODF 1.4 Part 3](https://docs.oasis-open.org/office/OpenDocument/v1.4/os/part3-schema/OpenDocument-v1.4-os-part3-schema.html): text contexts, links, lists, tables, styles, forms and drawing properties.
- [ODF 1.4 Part 4](https://docs.oasis-open.org/office/OpenDocument/v1.4/os/part4-formula/OpenDocument-v1.4-os-part4-formula.html): OpenFormula references and function semantics, including external-service and filename-sensitive cases.
- [BCP 47 language tag syntax](https://www.rfc-editor.org/rfc/rfc5646): well-formed tags and representation; no network or registry lookup is needed during document processing.
- [OASIS accessibility guidelines](https://docs.oasis-open.org/office/office-accessibility/v1.0/cs01/ODF_Accessibility_Guidelines-v1.0.html): historical guidance for review questions, not a replacement for current ODF markup or an accessibility conformance standard.
