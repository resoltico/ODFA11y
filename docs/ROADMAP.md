# Roadmap to v1.0.0

ODFA11y helps people inspect OpenDocument sources, make explicit accessibility decisions
and verify resulting publications. The route to v1.0.0 deepens document understanding,
completes accountable human review and establishes stable supported contracts. A clean
automated report is evidence about selected checks, never an accessibility certificate.

The current v0.7.0 candidate provides the source, library/CLI and verification workflows
described in the [README](../README.md), [API](API.md) and
[Accessibility scope and limits](ACCESSIBILITY.md). Publication requires qualification of
the exact release commit/artifacts and the configured release protections through the
[release procedure](RELEASING.md); a version declaration alone does not establish release.

This is the current plan, with completion criteria rather than promised dates. Each
feature includes library/CLI behavior, configuration, findings, preservation, documentation,
distribution contents and native evidence where applicable. Defects in supported
correctness or safety contracts are repaired as part of current work; later milestones
describe product expansion.

## Standards and design boundaries

Use the final OASIS Standard editions of [ODF 1.4](https://docs.oasis-open.org/office/OpenDocument/v1.4/os/)
and the bundled ODF 1.3 schemas for supported sources. Format validity, source semantics,
exporter capability, PDF/UA machine validation and human review are separate properties.
An ODF 1.4 feature must not silently upgrade an ODF 1.3 document.

Keep the parsed document model, family adapters, shared ODF primitives and generic
workflow. Replace a mechanism when evidence shows a simpler complete solution. Expansion
does not require a universal document model, plugin framework, Formula evaluator or PDF
repair engine. Reviewed changes before v1.0 may break configuration and APIs; update
affected consumers and describe required user action. OpenDocument is the product scope.

## v0.8.0 Text structure and navigation

Make text audits useful for longer, multilingual and structurally complex documents.

- Audit list structure, continuation identities, nesting and manually simulated list
  candidates. Separate structural defects from decisions about intended meaning; do not
  infer rewrites from typography.
- Expand hyperlink and internal-reference integrity checks. Treat `office:name` as a
  target name; preserve incoming references when addressing exporter constraints.
- Check bookmarks, cross-references, note anchors and note bodies for missing or
  ambiguous relationships in separate reading contexts. Add native fixtures for
  multi-column text, floating frames, sections and notes; report reading-order uncertainty.
- Resolve effective paragraph/inline language through named, automatic and direct styles,
  including script channels. Offer reviewed target-specific overrides while preserving
  authored text and unrelated overrides.
- Distinguish data tables, layout candidates and valid complex grids. Audit available
  header relationships and missing information without treating every merged cell as a
  failure. Keep unsupported or ambiguous remediation as an explicit refusal with native
  editing guidance.
- Deepen relationship checks and review coverage for already reported tracked, hidden
  and conditional content. Preserve separate reading contexts and protected content;
  accepting or rejecting revisions requires an explicit workflow.

Completion requires native documents combining these structures. Source findings, editable
decisions, PDF results and reading-order review must agree about their scope. Change
serialized contracts explicitly where needed and retain existing preservation/refusal
controls.

## v0.9.0 Data documents and review completion

Extend assistance across recognized families and connect automated evidence with
accountable human review.

- Add explicit spreadsheet header decisions where standard markup and Calc behavior can
  be established. Separate print repetition from header relationships; protect values,
  formulas, references, merges and hidden state. Broaden chart audits while exposing
  cached-data and external-provider limits without recalculation or fetching.
- Audit form labels, label/control references, keyboard order and grouping in supported
  families. Offer supplied label/description decisions only where native reload proves
  semantics. Do not execute submissions, scripts, SQL or connections.
- Inspect embedded chart and MathML accessibility at a bounded declared boundary, with
  origin locations and explicit unsupported internals. Keep source assurance separate
  from measured native PDF capability.
- Add a human-review record bound to source, plan and final-artifact digests, with explicit
  decisions, unresolved items and invalidation after relevant changes. Reuse evidence
  identities and review-item sources; a checkbox does not establish accessibility.
- Expand the corpus to independently authored ODF producers and documented screen-reader
  and keyboard review. Publish measured capabilities by family, producer and exporter
  version, with unsupported runtime combinations explicit.

Completion requires an end-to-end reviewed example for text, spreadsheet and presentation
or drawing, plus source-only examples for families without qualified PDF export. Positive
and negative controls must prove review invalidation and preservation. Native limitations
must remain precise support boundaries with user guidance; do not hide them through
conversion or PDF mutation.

## v1.0.0 Stable supported contracts

v1.0.0 establishes stable contracts for documented workflows. It does not promise automatic
accessibility, every ODF feature/producer or conforming PDF output from every family.

- Publish and stabilize library imports, CLI behavior, TOML schema, findings/logical
  locations, report/evidence formats and exit meanings. Remove unnecessary public surfaces
  before the freeze and define the subsequent compatibility policy.
- Complete a standards-to-capability review: every accessibility-relevant feature group
  in this plan has an implemented check, an explicit manual review step or a supported
  boundary. Tie claims to code, fixtures and results rather than an unverified inventory.
- Qualify the supported tool/OS matrix with real applications and representative authored
  documents. Publish native limits, human acceptance results and exact artifact identities.
- Demonstrate clean wheel/source-archive installation and the shortest documented workflow,
  with actionable errors for missing tools and unsupported inputs.
- Resolve release-blocking correctness/security findings, complete independent design and
  implementation review, and publish reproducible artifacts with provenance and release
  notes stating breaking actions and material limits.

Release v1.0.0 only when these criteria are satisfied. Subsequent work must respect the
stable supported contracts.

## Standards references

These sources guide feature semantics; they do not establish application behavior.

- [ODF 1.4 Part 2](https://docs.oasis-open.org/office/OpenDocument/v1.4/os/part2-packages/OpenDocument-v1.4-os-part2-packages.html): packages, signatures, metadata and package IRIs.
- [ODF 1.4 Part 3](https://docs.oasis-open.org/office/OpenDocument/v1.4/os/part3-schema/OpenDocument-v1.4-os-part3-schema.html): text, links, lists, tables, styles, forms and drawings.
- [ODF 1.4 Part 4](https://docs.oasis-open.org/office/OpenDocument/v1.4/os/part4-formula/OpenDocument-v1.4-os-part4-formula.html): OpenFormula declarations and semantics.
- [BCP 47 language tag syntax](https://www.rfc-editor.org/rfc/rfc5646): well-formed tags and representation.
