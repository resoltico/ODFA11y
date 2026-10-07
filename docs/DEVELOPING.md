# Development

## Restore the environment

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run from
the source directory:

```bash
uv sync --locked
```

Python 3.14 is the baseline. [.python-version](../.python-version) selects the
development interpreter, which uv installs when needed.
[pyproject.toml](../pyproject.toml) defines the supported Python range, dependency
ranges and pinned build, lint, type-check and boundary tools. [uv.lock](../uv.lock) records the resolved
runtime and development dependencies.

To refresh dependencies deliberately, review their changes, run `uv lock --upgrade`,
restore the environment again, and repeat the required checks. Update the pinned
build backend and `dev` group constraints in `pyproject.toml` when changing those tools.
Dependabot proposes updates to the locked environment and workflow actions weekly; the `Dependency audit` workflow also checks the locked dependencies against advisories every week.
Development tools live in the `dev` dependency group, which uv installs by default;
they are not part of the published package metadata.

## Required checks

```bash
uv run --no-sync python tools/check_quality.py
uv run --no-sync ruff check . --ignore-noqa
uv run --no-sync ruff format --check .
uv run --no-sync ty check
uv run --no-sync tach check
uv run --no-sync tach check-external
uv run --no-sync pytest --cov
uv build
```

Ruff enables all rules, including preview rules, at its pinned version. Exceptions
belong only in the root `pyproject.toml`, with a preceding reason comment for each
entry. The policy checker rejects inline lint/formatter directives and separate
Ruff configuration files. Apply routine changes with `ruff check . --fix` and
`ruff format .`; review unsafe fixes before accepting them.

Every authored Python file must fit within the configured physical-line limit,
including blanks and docstrings. There are no file-specific size exemptions or
historical baselines. Split oversized modules by responsibility. The policy
checker includes tests, tools and hidden directories; generated environments,
build outputs, Git metadata and Python/Ruff caches are excluded. Function
complexity, branch, argument, return and statement limits are also defined in
`pyproject.toml`; the few API exceptions have explicit reasons there.

pytest enables all strictness options and treats warnings as errors. Tests create
synthetic ODF/PDF fixtures (`tests/documents.py` builds every document kind as a package and as flat XML) rather than storing customer documents. The TOML example
is extracted directly from [Configuration](CONFIGURATION.md#example) and validated
through the real loader.

## Writer regression corpus

`tests/corpus` holds small documents that a real LibreOffice Writer wrote, with a
[README](../tests/corpus/README.md) naming each one's purpose and provenance and a
`manifest.toml` recording, per file, the exact audit rule ids, the rule ids left after the
standard remediation plan, the schema-violation count and the SHA-256. `tests/test_corpus.py`
and `tests/test_corpus_remediation.py` check all of it, and an integration test runs the
pipeline on some of the documents. The files are marked binary in `.gitattributes`; they ship
in the source archive with the rest of `tests/`.

The Writer corpus hyperlink pipeline test compares the exported PDF with real veraPDF.
When LibreOffice omits link descriptions, it requires `PDF019`, a failed PDF audit and
skipped downstream stages; other failures are rejected. Green CI proves that the defect
is detected, while the other corpus pipeline cases must complete successfully.


To add or change a document:

1. Add or edit its source in `tests/corpus/sources/` (HTML for what Writer's HTML import
   expresses, flat XML for the rest).
2. With `soffice` on the path, run `sh tests/corpus/build.sh` from the repository root. It
   rewrites every document, and Writer's timestamps change every file's bytes, so only commit
   the documents that changed on purpose; restore the others with `git checkout`.
3. Audit the new documents, decide their expected rule ids by reading the findings, and list
   the document in `manifest.toml` with its rule ids, schema-violation count and
   `sha256sum` hash. List it in the corpus README too. Let the tests tell you which
   expectation is wrong; do not copy their output without reading it.
4. Update the LibreOffice version in the manifest and README when regenerating with another
   one.

## Types, boundaries and properties

[ty](https://github.com/astral-sh/ty) checks `src`, `tests` and `tools` using
`types-lxml` for lxml's API. Select ODF elements through
`odfa11y.odf.select_elements`: it returns only element nodes, so callers never handle
lxml's XPath union result. Fix a type error in the code rather than suppressing it.

[Tach](https://github.com/tach-org/tach) enforces the package layering and public
interfaces in [tach.toml](../tach.toml); see [Architecture](ARCHITECTURE.md#packages-and-dependency-rules).
Document families are nested modules (`odfa11y.families.text`, `odfa11y.families.spreadsheet`): tach rejects a family
importing another, or any package below the registry importing one. When a package needs a
new dependency, change the design first and `tach.toml` only if the new direction is
intended. `tools/check_quality.py` adds the check tach cannot make, that no core package
names a family's XML elements (`qn("text", …)`, `//table:…`); add such code to the family's
package. [Adding a family](ARCHITECTURE.md#adding-a-family) lists every step.

[Hypothesis](https://hypothesis.readthedocs.io/) properties in
`tests/test_properties.py` state invariants over generated input: lossless address
splitting, text-preserving linkification, package round trips, rejection of arbitrary or
corrupted archives and configuration with `PackageError`/`ConfigError` only, and that any
applicable subset of operations keeps a schema-valid document schema-valid and is
idempotent. The profile
in `tests/conftest.py` is deterministic and bounded; a failure is reproducible by
rerunning pytest, and a found counterexample belongs in an `@example` beside a fix.
Coverage uses branch measurement with the floor in `pyproject.toml`; raise the floor
when coverage rises, never lower it to pass.

## External integration and CI

Tests marked `integration` run the real LibreOffice export and real veraPDF
validation. They skip when an executable is absent, so a unit-only run does not prove
integration; set `ODFA11Y_REQUIRE_INTEGRATION=1` to make a missing application fail:

```bash
ODFA11Y_REQUIRE_INTEGRATION=1 uv run --no-sync pytest -m integration
```

[Checks](../.github/workflows/checks.yml) runs three kinds of job:

- **Static analysis** (Linux): workflow syntax and security, secret scan, dependency
  advisories, policy, Ruff, ty and tach.
- **Quality** (Linux, macOS, Windows; the job is `test` in the workflow): unit tests (with coverage on Linux), a build of
  the source archive and wheel, and unit tests against the wheel installed with
  hashed locked dependencies, including metadata, license and `py.typed` checks.
- **Integration** (Linux, macOS, Windows): installs LibreOffice (the distribution package on
  Linux, the current release on macOS and Windows) and a checksum-pinned veraPDF with
  `tools/install_verapdf.py`, then runs the integration tests (real exports, real
  validation, the full pipeline) with `ODFA11Y_REQUIRE_INTEGRATION=1`. PDF tagging and
  pagination are exporter behaviour, so passing on one operating system says little about
  another. LibreOffice versions are not pinned; the job logs the version it ran with, and
  the evidence record of any run carries it.
- **CI gate**: waits for the three jobs above and fails unless all succeeded. It is the
  only check a branch ruleset should require; see [Releasing](RELEASING.md#repository-settings).

Workflow syntax and shell commands are checked by the actionlint version pinned
in the workflow. It uses the Linux runner's Go toolchain and ShellCheck. With that
actionlint version installed, validate locally using:

```bash
actionlint .github/workflows/checks.yml
```

The workflow uses read-only repository permissions, pinned actions, bounded job
runtimes and PR cancellation; checkout credentials are not persisted. It supports
manual runs. Runner images and LibreOffice packages follow their upstream stable
distributions, so the lockfile does not freeze the complete operating system.

veraPDF is a separately installed Java CLI used when an operator explicitly requests
`--verapdf`. CI validates a LibreOffice export with a pinned veraPDF release; update
`ODFA11Y_VERAPDF_VERSION` and its checksum together. Its machine-validation scope is
described in [Accessibility and limits](ACCESSIBILITY.md).

## Packaging

`uv build` is the build frontend. It reads `[build-system]` in
`pyproject.toml` and installs the pinned [Hatchling backend](https://hatch.pypa.io/latest/config/build/) into an isolated build
environment. Contributors do not need the Hatch application or a `setup.py`.

Build selection is centralized under `[tool.hatch.build.targets]`:

- The source archive (`sdist`, `.tar.gz`) includes the package sources, docs, tests,
  policy tools, workflow, lockfile, boundary rules and interpreter selection. Hatchling also
  includes the declared README/license and project configuration.
- The wheel (`.whl`) contains the importable `odfa11y` packages, `py.typed`, CLI entry
  point, metadata and license. Repository docs and tests are not runtime package files.

The backend reads the version from `src/odfa11y/__init__.py`; keep it as the single
version source. Build after moving files or changing inclusion rules, inspect both
archives, and verify an isolated wheel installation. A successful source-tree test
run alone does not prove that packaging included the required modules.

## Contribution invariants

1. Audits remain read-only and findings retain stable rule IDs.
2. Ambiguous semantic choices require explicit input.
3. Structural editing preserves normalized document wording before saving.
4. Package output retains the first/uncompressed `mimetype` invariant; untouched members stay byte-identical.
5. Evidence carries no local path and is never read outside its directory.
6. Test new checks and meaningful rejection paths; verify external boundaries when claimed.
7. Distinguish PDF diagnostics, machine validation and human acceptance.
8. Keep customer/private documents out of source control and test fixtures.
9. Family-specific names, rules and operations stay inside the family's package.

Read [AGENTS.md](../AGENTS.md) before changing the project and
[Architecture](ARCHITECTURE.md) for implementation boundaries. Follow
[Releasing](RELEASING.md) for starting a release; record release outcomes in the changelog's Unreleased
section as work lands.


## Audit hygiene

Install the locked optional audit tools when performing a security/release review:

```bash
uv sync --locked --group audit
uv run --no-sync zizmor --offline --persona pedantic --no-ignores --strict-collection .github/workflows
uv export --locked --group audit --no-emit-project --output-file /tmp/odfa11y-audit.txt > /dev/null
uv run --no-sync pip-audit --strict --require-hashes --disable-pip -r /tmp/odfa11y-audit.txt
```

Audit findings need a reproduced condition, an explanation of the property affected,
and a rejection/control case where practical. Fix concrete findings; do not add
blanket exceptions or lower assurance to get a green result. Preserve failures and
state exactly what inputs, tool versions and external boundaries were checked.
Known-advisory scans require network access and only establish the database's
findings at that time. The CI secret scan uses the Gitleaks version pinned in the
workflow, redacts output and scans the fetched Git history. With that version
installed locally, use `gitleaks dir . --redact --ignore-gitleaks-allow` for a working
folder or `gitleaks git --redact --ignore-gitleaks-allow` for history. Scan intended
publication files separately from third-party environments/build caches.
