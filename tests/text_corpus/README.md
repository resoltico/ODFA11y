# Writer text-structure corpus

These invented inputs were saved by the LibreOffice version in [manifest.json](manifest.json).
The manifest binds each ODT and its [authoring source](sources) by SHA-256 and records its
strict-schema violation baseline. Tests verify inventory, producer, bytes and actual behavior.

| Feature | Positive / negative scope |
| --- | --- |
| Lists | Real nested/continued lists versus typed numeric paragraphs. |
| References | Existing bookmark/footnote relationships versus a missing internal destination. |
| Language | English/French local declarations versus explicitly unspecified channels. |
| Tables | Valid merged headers, ambiguous intent and declared data lacking headers. |
| Visibility | Plain current text versus tracked deletion, hidden section and uncertain layout. |

Regenerate a selected feature with
`uv run --no-sync python -m tools.build_text_corpus FEATURE` (`lists`, `references`,
`language`, `tables`, `visibility`). Review changed source/native/PDF results before retaining
new bytes. Regeneration reproduces intended semantics, not byte-identical native output.
Writer numeric cells need explicit number formatting to retain their types.

Positive/negative refer to the feature under test. Short fixtures still have a PDF heading
warning; source-valid reference relationships can have failing exported annotations.
See [measured PDF results](../../docs/verification/0.8.0-text-exports.json) and
[accessibility boundaries](../../docs/ACCESSIBILITY.md). No fixture is an accessibility certificate.
