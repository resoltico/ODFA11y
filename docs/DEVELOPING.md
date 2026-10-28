# Development

## Restore the environment

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then:

```sh
uv sync --locked --group audit
uv run --no-sync odfa11y doctor
```

[.python-version](../.python-version) selects development Python; [pyproject.toml](../pyproject.toml)
owns supported versions, dependencies, build/tool pins and analyzer policy. [uv.lock](../uv.lock)
restores Python inputs. Native installer/action/Go pins and vendor checksums live in
[Checks](../.github/workflows/checks.yml). Verify downloads before installation.

Refresh versions from PyPI, vendor GitHub releases, python.org, documentfoundation.org and
verapdf.org, including majors. Update constraints/pins, run `uv lock --upgrade`, restore
locked groups and repeat all gates. Security alerts/audits remain vulnerability signals;
Dependabot version proposals are not a release-version authority.

## Required checks

Run on stable inputs, using focused checks while iterating:

```sh
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync python -m tools.check_quality
uv run --no-sync tach check
uv run --no-sync tach check-external
uv run --no-sync python -m tools.generate_reference --check
uv run --no-sync pytest -m 'not integration' --cov
ODFA11Y_REQUIRE_INTEGRATION=1 uv run --no-sync pytest -m integration -n 2 --max-worker-restart=0 --cov --cov-append
uv build
```

Run unit then native coverage sequentially; they share `.coverage`. Keep unit tests
sequential for hostile-input timing controls. Native workers have separate inputs,
outputs and LibreOffice profiles; worker crashes fail without retry. Required native mode
turns absent tools into failures. Record versions, failures/fixes, skipped work and unavailable
platforms. Branch coverage must remain at least 88%; inspect `coverage json` totals.

Ruff checks all authored Python, including hidden/ignored source; `tools.check_quality`
passes explicit authored paths to ty. Generated environments/caches/root build outputs are
excluded, while nested authored `build`/`dist` names remain in scope. Complexity/branch
limits stay at 10; module cohesion is reviewed separately from size. Narrow justified
inline suppressions are checked for staleness; file-level ignores are for tests only.
See [architecture](ARCHITECTURE.md) and [AGENTS.md](../AGENTS.md).

CI requires **CI gate**, aggregating static/security, platform Quality and Integration jobs;
skipped/cancelled required jobs fail it. Native installers are checksum-pinned on all three
platforms. Runner images still vary; local macOS results do not establish Linux/Windows
behavior. [Releasing](RELEASING.md) defines exact-revision publication qualification.

## Generate documentation

```sh
uv run --no-sync python -m tools.generate_reference
uv run --no-sync python -m tools.generate_reference --check
```

One module generates rules, plan fields, CLI/options/exits, schema listing and measured
capabilities. The current [doctor measurement](measurements/doctor.json) supplies the capability matrix;
update it only from an actual qualified native run. Generation never runs native tools. Keep task guides short
and link to the canonical [boundaries](ACCESSIBILITY.md). Check Markdown links/anchors.

## Native document fixtures

Use invented content and independent positive/negative controls. Inspect source relationships,
native reload, exported PDF and human-review scope together; a passing detection control
is not an accessible publication. Fixtures/hashes alone do not establish semantics.

- [Writer corpus](../tests/corpus/README.md): edit `sources`, run its `build.sh`, review results
  and update manifest expectations/producer/hashes. Retain unrelated fixture bytes.
- [Text structure corpus](../tests/text_corpus/README.md): run
  `uv run --no-sync python -m tools.build_text_corpus FEATURE`; sources and manifest record
  the real Writer save. Numeric values need the [explicit number format](../tests/fixtures/table_formats.py)
  to survive import as numeric data. Do not weaken classification to accept stripped types.
- [Family corpus](../tests/family_corpus/README.md) and
  [focused reproductions](../tests/reproductions/README.md): use disposable profiles for trusted
  authoring macros. Inspection itself executes no macros, SQL or connections.

Shared fixtures live under `tests/fixtures`; tests follow owner packages and `tests/native`.
Eight-family conformance covers the shared contracts.
Hypothesis uses the deterministic required profile; `--hypothesis-profile=smoke` is for
iteration only. Successful pytest scratch is cleaned best-effort; failed/abrupt runs can
retain evidence. These settings do not impose a disk quota or OS sandbox.

## Packaging

`uv build` uses the pinned backend without the Hatch application or `setup.py`. Source
archives carry contributor sources/docs/tests/tools/workflows/locks; wheels carry runtime
packages/resources, notices, metadata and `py.typed`. `[project].version` is authoritative;
run `uv lock` and `uv sync --locked` after changing it.

```sh
uv run --no-sync python -m tools.check_release v0.8.0 dist
```

The checker requires exact contributor file names/bytes, runtime resources and metadata.
Stage intended additions/deletions before checking Git inventory. Rebuild twice and compare
bytes. Extract the sdist outside the checkout, restore locked inputs and repeat checks/build
without `.git`. Test the wheel in an isolated environment with hashed locked dependencies,
using the extracted contributor tests and [root-only examples](../tools/core_examples.py).
The workflow is the executable authority for this contributor/distribution flow.

## Audit hygiene

With pinned actionlint/Gitleaks available and the audit group restored:

```sh
actionlint .github/workflows/checks.yml .github/workflows/audit.yml
uv run --no-sync zizmor --offline --persona pedantic --no-ignores --strict-collection .github/workflows
uv export --locked --group audit --no-emit-project -o /tmp/odfa11y-audit.txt > /dev/null
uv run --no-sync pip-audit --strict --require-hashes --disable-pip -r /tmp/odfa11y-audit.txt
gitleaks git --redact --ignore-gitleaks-allow
```

Advisory scans describe their database at that time. Scan intended publication contents;
exclude third-party environments/caches and never submit private documents or credentials.
Use operating-system isolation/resource limits for untrusted native processing.
