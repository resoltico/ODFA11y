# Developing

## Clean checkout

Use the uv version required by [pyproject.toml](../pyproject.toml). The supported Python
range is declared there; [.python-version](../.python-version) selects the contributor
interpreter. The pinned build backend and [uv.lock](../uv.lock) define reproducible Python
inputs. Supported dependency ranges are not alternative lockfiles.

```sh
uv sync --locked --group audit
```

LibreOffice and veraPDF are external prerequisites for native integration. Missing tools
are preparation failures, not a passing or optional validation result. CI installs the
versions and verified hashes in [native_versions.toml](../tools/native_versions.toml)
through the Python installer helpers. See [boundaries](ACCESSIBILITY.md).

## Required checks

[tools.check](../tools/check.py) owns check commands and stops at the first failure:

```sh
uv run --no-sync python -m tools.check lint types boundaries reference unit
uv run --no-sync python -m tools.check integration
uv run --no-sync python -m tools.check build release audit
```

With both native applications installed, `python -m tools.check all` runs the full set.
The dependency `audit` stage restores no packages: it audits the locked hashed inputs
using the already-restored audit group. Local native checks require the real tools;
CI treats a missing prerequisite or skipped native test as a failure.

Use focused pytest selections while changing an owner, then run its required gates. Unit
tests use automatic workers and retain the 88% coverage gate; integration is selected by
`tests/integration/`, uses two workers and does not gate coverage. Diagnose complete relevant
failure output before retrying. Do not weaken hostile-input controls or add timing/size gates.

[Checks](../.github/workflows/checks.yml) runs the full entry point on Linux, macOS and
Windows with both native applications. **CI gate** rejects failed, cancelled or skipped
required jobs. Local macOS evidence does not establish the other platforms' behavior.

## Generated references

```sh
uv run --no-sync python -m tools.generate_reference
uv run --no-sync python -m tools.check reference
```

One generator derives CLI/options, rules and their historical mapping, plan fields, schemas,
glossary and measured capabilities. The [doctor measurement](measurements/doctor.json)
is the observation authority for capabilities. Refresh it only from an actual native run;
generation itself never runs native tools.

## Native document fixtures

[One corpus](../tests/corpus/README.md) has one manifest with family/purpose tags, observed
producer identities, hashes and expected outcomes. Authoring inputs and stored native output
serve different roles. Hashes identify bytes; independent semantic and hostile-input controls
establish behavior. All content must be invented.

Use [tools.build_corpus](../tools/build_corpus.py) to produce selected artifacts in a new
output directory. It uses ordinary conversion where available and trusted repository BASIC
modules in private disposable profiles where native application services are required.
It never updates the manifest or preservation expectations. Inspect native output, XML,
schema results and relevant controls before deliberately replacing a fixture. Retain unrelated
fixture bytes and the historical preservation outcomes.

Shared constructors live in `tests/fixtures`; tests follow their source owners. Record tests
call `assert_record_schema` explicitly. Hypothesis' deterministic required profile is the
qualification default; the smoke profile is for iteration only. Failed/abrupt process tests
may retain useful scratch evidence; these settings are not an operating-system sandbox.

## Packaging

`tools.check build release` uses the pinned backend, checks distribution metadata/resources
and notices, rebuilds from the extracted source archive byte-for-byte, then verifies an
isolated installed wheel with locked hashed runtime dependencies. The
[root-only examples](../tools/core_examples.py) run outside the checkout under that installed
interpreter, with import and normative-schema provenance checks.

The sdist contains `pyproject.toml`, `README.md`, `LICENSE`, `src/` and its notices, plus
required generated package metadata. Contributor tests, tools, CI files, locks and docs
are checkout inputs and do not ship in it. Stage intended additions/deletions before Git
inventory checks. `[project].version` is authoritative; changing it is a separately
authorized release action. See [Releasing](RELEASING.md).

## Audit hygiene

```sh
actionlint .github/workflows/checks.yml .github/workflows/audit.yml
uv run --no-sync zizmor --offline --persona pedantic --no-ignores --strict-collection .github/workflows
uv run --no-sync python -m tools.check audit
gitleaks git --redact --ignore-gitleaks-allow
```

Advisory scans describe their database at that time. Inspect intended publication contents,
exclude third-party environments/caches and never publish private documents or credentials.
