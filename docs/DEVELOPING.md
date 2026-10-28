# Development

## Restore the environment

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run from
the source directory:

```bash
uv sync --locked
```

[.python-version](../.python-version) selects the development interpreter; uv installs it
when needed. [pyproject.toml](../pyproject.toml) declares the supported Python range,
dependency constraints, pinned build/analyzer tools and development groups.
[uv.lock](../uv.lock) records resolved dependencies. The `dev` group is installed by
default and is not part of runtime package metadata.

Native export/integration also needs the supported LibreOffice and veraPDF installations;
see [prerequisites](../README.md#start-here) and run `uv run --no-sync odfa11y doctor`.
The minimum LibreOffice version is enforced by `find_soffice` in
[pdf/export.py](../src/odfa11y/pdf/export.py). Exact CI tool/installer inputs are declared
in [Checks](../.github/workflows/checks.yml), with installer checksums where configured.

To refresh dependencies, query PyPI's JSON API, vendor GitHub releases, python.org,
documentfoundation.org and verapdf.org directly. Review all current releases, including
majors; update constraints, exact tool pins and action commit SHAs from those sources.
Verify native installers against the vendor's published SHA-256 before installation.
Run `uv lock --upgrade`, restore with `uv sync --locked --group audit`, then repeat the
static, unit, native, workflow, dependency-audit and distribution checks below.
Dependabot security alerts and the scheduled [dependency audit](../.github/workflows/audit.yml)
remain vulnerability signals; version-update PRs are not release-version sources.

## Required checks

Run inexpensive static checks before the complete test/build gates:

```bash
uv run --no-sync python -m tools.check_quality
uv run --no-sync ruff check . --ignore-noqa
uv run --no-sync ruff format --check .
uv run --no-sync python -m tools.check_quality --types
uv run --no-sync tach check
uv run --no-sync tach check-external
uv run --no-sync pytest -m 'not integration' --cov --durations=10
ODFA11Y_REQUIRE_INTEGRATION=1 uv run --no-sync pytest -m integration -n 2 --max-worker-restart=0 --cov --cov-append --durations=10
uv build
```

The local test commands select complementary sets and append native coverage to the
unit coverage. Run them in order because they share the coverage data file. Keep unit
tests sequential so hostile-input timing controls have predictable CPU availability.
Integration uses two workers with separate documents, outputs and LibreOffice profiles;
a worker crash fails without retry. Targeted tests remain sequential by default.

Use targeted checks while iterating, then required checks on stable delivered inputs.
Independent static checks may run together; do not edit or format their inputs during a
verification batch. Record failures, skips, tool identities and unavailable platforms.

### Policy, lint and types

Ruff enables its pinned complete rule set, including preview rules. Public APIs use NumPy
docstrings; the formatter owns trailing commas. All exceptions live in root
`pyproject.toml`, with specific reasons, exact current rules, authored scopes and actual
suppressed diagnostics. The policy gate probes the unsuppressed configuration and rejects
unused/overlapping masks, inherited analyzer configuration, reduced rule selection,
disabled type rules and inline lint/format/type/security suppressions.

The shared inventory includes hidden and Git-ignored authored Python. Generated
environments/caches and root build/distribution outputs are excluded; a nested domain
directory named `dist` or `build` remains authored. Type checking receives explicit paths;
Ruff uses explicit project exclusions. Every authored file must fit the physical-line
limit, including blanks/docstrings, and function complexity limits apply to source, tests
and tools. Fix responsibility or code issues rather than hiding files or diagnostics.

Apply routine fixes with `uv run --no-sync ruff check . --fix` and
`uv run --no-sync ruff format .`; review unsafe fixes before accepting them.

[ty](https://github.com/astral-sh/ty) uses `types-lxml` for lxml's API. Select ODF elements
through `odfa11y.odf.select_elements` so callers receive element nodes rather than lxml's
XPath union type. [Tach](https://github.com/tach-org/tach) enforces declared dependencies
and public interfaces in [tach.toml](../tach.toml). Review the design before changing an
edge. The policy checker also rejects family-specific XML selection in orchestration;
shared vocabulary belongs in `content`, family semantics in its adapter. See
[Architecture](ARCHITECTURE.md#packages-and-dependency-rules).

### Tests and generated inputs

pytest enables strict options and treats warnings as errors. Tests use synthetic ODF/PDF
fixtures and invented native documents, never customer material. Helpers in
`tests/documents.py` create package/flat fixtures, including deliberately unsupported
representations used as rejection controls. A valid flat office-body Formula representation
is not claimed. The [Configuration example](CONFIGURATION.md#example) is loaded directly
by a test.

[Hypothesis](https://hypothesis.readthedocs.io/) properties in `tests/test_properties.py`
cover address splitting, text-preserving linkification, package round trips, controlled
errors for malformed inputs and schema-preserving/idempotent operation subsets.
`tests/conftest.py` defines the deterministic required profile and a smaller smoke profile:

```bash
uv run --no-sync pytest tests/test_properties.py --hypothesis-profile=smoke
```

Smoke does not replace required properties. Profiles have no per-example deadline;
regression examples, rejected draws and shrinking mean `max_examples` is not a total
invocation limit. CI job timeouts bound a job. Store useful counterexamples beside their
regression tests. File-based properties use a temporary directory per example.

Successful `tmp_path` call outputs are removed; failed-call outputs retain pytest's
configured session history. A later teardown failure can lose a successful call's files.
Cleanup is best effort, and explicit `--basetemp` leaves session-root cleanup to the caller.
These settings bound retention, not total disk allocation. Native scratch, caches and
abrupt termination prevent a workspace byte guarantee; use a filesystem quota for a hard
limit. Coverage policy and its branch-measurement floor are in `pyproject.toml`.

## Native document fixtures

### Writer regression corpus

`tests/corpus` contains invented Writer documents. Its [README](../tests/corpus/README.md)
describes every input, and `manifest.toml` is authoritative for artifact identity, producer,
expected findings, post-plan findings and schema violations. The corpus tests verify
these expectations; native pipeline tests verify actual export behavior. A producer
version records an input's provenance, not a separate supported-runtime lane.

To add or change a fixture:

1. Edit the source in `tests/corpus/sources/` (HTML or flat XML).
2. Run `sh tests/corpus/build.sh` with a supported `soffice` on `PATH`. This regenerates
   every document and may change producer metadata/bytes; retain only intended changes.
3. Read actual audit/schema/native results, decide expected behavior and update the
   manifest's findings, producer and hashes. Keep the corpus README's filename inventory
   synchronized. Regeneration reproduces semantics, not byte-identical native output.
4. Run corpus audit, remediation and native pipeline checks. Positive controls must retain
   intended content; rejection cases must fail for the expected reason.

### Family and focused reproductions

[Native family fixtures](../tests/family_corpus/README.md) have their own manifest and
authoring sources. Chart/Image assemblies distinguish native components from standalone
native save/export support. Use disposable profiles for trusted fixture-authoring macros;
the library's source inspection does not execute macros or Base queries.

[Focused reproductions](../tests/reproductions/README.md) exercise text contexts and native
link behavior. Inspect source XML, protected content and actual exported output together.
An expected exporter failure is a passing detection control, not evidence of an accessible
publication. Never suppress unrelated native failures.

## External integration and CI

Tests marked `integration` run real LibreOffice and veraPDF. Missing tools can skip tests
locally; `ODFA11Y_REQUIRE_INTEGRATION=1` requires them and turns absence into failure.
A unit-only result does not establish native integration.

[Checks](../.github/workflows/checks.yml) defines:

- **Static analysis**: policy, Ruff, types, Tach, workflow syntax/security, known dependency
  advisories and a redacted Git-history secret scan.
- **Quality** on Linux/macOS/Windows: unit tests, distribution build/inspection, an extracted
  source-archive contributor flow, and isolated installed-wheel checks/tests. Linux also
  measures unit coverage and compares rebuilt distribution bytes.
- **Integration** on Linux/macOS/Windows: configured native installations, doctor output
  and required real export/validation/pipeline tests. These hosted commands do not append
  integration coverage to the Quality job's coverage.
- **CI gate**: waits for all three job groups and requires success; skipped/cancelled jobs
  fail it. It is the single branch-protection check documented in
  [Releasing](RELEASING.md#repository-settings).

The workflow declares tool pins, installer checksums, job timeouts, permissions and cache
policy. Linux/Windows use pinned LibreOffice installers; macOS follows the configured
current distribution. Runner images also vary. The lockfile does not freeze the OS or
complete native toolchain. Native results must carry the actual tool identity.

Checks run for main/version-tag pushes, pull-request merge commits and manual dispatch.
PR runs can cancel superseded PR runs. Default permissions are read-only; checkout does
not persist credentials. Only the draft-release job receives write/attestation permissions.
Cache restoration is bypassed where the workflow requires release isolation; cache policy
does not establish a storage quota.

With the workflow's actionlint version installed, validate both workflow files locally:

```bash
actionlint .github/workflows/checks.yml .github/workflows/audit.yml
```

The workflow uses the runner's Go toolchain and ShellCheck for this gate. Native installer
steps verify configured hashes before execution and have bounded job/step runtimes;
transport retries are not a hard end-to-end download deadline.

## Packaging

`uv build` reads the pinned Hatchling backend in `[build-system]` and builds in isolation.
Contributors need neither the Hatch application nor `setup.py`. Build selection is
centralized in `[tool.hatch.build.targets]`:

- Source archives include package sources, documentation, tests/corpus inputs, tools,
  workflows, dependency lockfile, boundary rules and environment/project configuration.
- Wheels include runtime packages/resources, CLI entrypoint, metadata, notices and
  `py.typed`. Repository docs/tests are contributor materials, not runtime package files.

`[project].version` is the version authority. Runtime reporting derives installed
distribution metadata; after changing the declaration, run `uv lock` and
`uv sync --locked` to refresh the lockfile/editable environment.

After moving files or changing inclusion rules, build and inspect both distributions.
Run the release checker with the declared version:

```bash
uv run --no-sync python -m tools.check_release vVERSION dist
```

It checks distribution metadata/resources and compares source-archive regular-file names
and bytes with tracked contributor inputs; generated root `PKG-INFO` and directories are
the only packaging additions. Deleted files must be removed from the tracked inventory,
and new deliverables must be tracked. Duplicates, unsafe names, missing/altered contributor
materials and unexpected authored files fail.

To verify the contributor boundary, extract the archive outside the checkout, enter its
top directory, run `uv sync --locked` and repeat static/unit checks, build and release
inspection there. No `.git` is needed. The extracted inventory excludes configured root
generated outputs and recursive Python/pytest/Ruff/Hypothesis caches; nested authored
`build`, `dist` and `PKG-INFO` names remain included. Required native checks still need
real tools.

Verify the wheel from a separate environment using locked/hashed dependencies and the
extracted contributor tests. Check imports come from that environment, metadata matches
the project declaration, and notices, schema provenance and runtime resources are present.
The Quality job implements this flow on all three platforms.

## Contribution invariants

Audits remain read-only. Semantic choices require explicit reviewed input. Remediation
preserves family-specific content/references and opaque resources, uses schema comparison
when available, and publishes atomically to a separate destination. Evidence diagnostics
redact local directories; document payloads preserve authored content. Verification rejects
unsafe paths within the stated stable-directory prerequisite. Automated checks, native
application evidence and human acceptance establish different properties.

Read [AGENTS.md](../AGENTS.md) and [Architecture](ARCHITECTURE.md) before changes.
Update affected documentation, provide meaningful behavior/rejection evidence and follow
[Releasing](RELEASING.md) for release work.

## Audit hygiene

Install the locked optional audit tools for security/release review:

```bash
uv sync --locked --group audit
uv run --no-sync zizmor --offline --persona pedantic --no-ignores --strict-collection .github/workflows
uv export --locked --group audit --no-emit-project --output-file /tmp/odfa11y-audit.txt > /dev/null
uv run --no-sync pip-audit --strict --require-hashes --disable-pip -r /tmp/odfa11y-audit.txt
```

Known-advisory scans need network access and establish findings from that database at
that time. With the workflow's Gitleaks version installed, run
`gitleaks dir . --redact --ignore-gitleaks-allow` on intended publication files or
`gitleaks git --redact --ignore-gitleaks-allow` for Git history. Keep third-party
environments/caches separate from publication scans. Do not include private documents,
credentials or identifiable production material in fixtures or reports submitted for review.
