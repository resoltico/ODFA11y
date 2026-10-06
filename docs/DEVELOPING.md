# Development

## Restore the environment

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run from
the source directory:

```bash
uv sync --locked --extra dev
```

Python 3.14 is the baseline. [.python-version](../.python-version) selects the
development interpreter, which uv installs when needed.
[pyproject.toml](../pyproject.toml) defines the supported Python range, dependency
ranges and pinned build/lint tools. [uv.lock](../uv.lock) records the resolved
runtime and development dependencies.

To refresh dependencies deliberately, review their changes, run `uv lock --upgrade`,
restore the environment again, and repeat the required checks. Update the pinned
build backend or Ruff constraints in `pyproject.toml` when changing those tools.
A plain `python -m pip install -e '.[dev]'` is also supported on Python 3.14, but
resolves dependency ranges rather than reproducing the lockfile.

## Required checks

```bash
uv run --no-sync python tools/check_quality.py
uv run --no-sync ruff check . --ignore-noqa
uv run --no-sync ruff format --check .
uv run --no-sync pytest
uv run --no-sync python -m build
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
synthetic ODT/PDF fixtures rather than storing customer documents. The TOML example
is extracted directly from [Configuration](CONFIGURATION.md#example) and validated
through the real loader.

## External integration and CI

The LibreOffice export test is marked `integration`. It skips when the executable
is absent, so a unit-only run does not prove export integration:

```bash
uv run --no-sync pytest -m integration
```

[Checks](../.github/workflows/checks.yml) restores locked environments on Linux and
macOS and Windows. Linux installs LibreOffice and runs the full suite; macOS and
Windows run unit tests.
All three platforms build a wheel from the source archive, install it into an isolated
environment with hashed locked dependencies, verify metadata/license contents and
run unit tests against that installed wheel.

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

CI currently does not run a real veraPDF integration test. veraPDF is a separately
installed Java CLI used when an operator explicitly requests `--verapdf`. Its
machine-validation scope is described in [Accessibility and limits](ACCESSIBILITY.md).

## Packaging

`python -m build` is the build frontend. It reads `[build-system]` in
`pyproject.toml` and installs the pinned [Hatchling backend](https://hatch.pypa.io/latest/config/build/) into an isolated build
environment. Contributors do not need the Hatch application or a `setup.py`.

Build selection is centralized under `[tool.hatch.build.targets]`:

- The source archive (`sdist`, `.tar.gz`) includes the package sources, docs, tests,
  policy tools, workflow, lockfile and interpreter selection. Hatchling also
  includes the declared README/license and project configuration.
- The wheel (`.whl`) contains the importable `odfa11y` package, CLI entry point,
  metadata and license. Repository docs and tests are not runtime package files.

The backend reads the version from `src/odfa11y/__init__.py`; keep it as the single
version source. Build after moving files or changing inclusion rules, inspect both
archives, and verify an isolated wheel installation. A successful source-tree test
run alone does not prove that packaging included the required modules.

## Contribution invariants

1. Audits remain read-only and findings retain stable rule IDs.
2. Ambiguous semantic choices require explicit input.
3. Structural editing preserves normalized document wording before saving.
4. ODT output retains the first/uncompressed `mimetype` invariant.
5. Test new checks and meaningful rejection paths; verify external boundaries when claimed.
6. Distinguish PDF diagnostics, machine validation and human acceptance.
7. Keep customer/private documents out of source control and test fixtures.

Read [AGENTS.md](../AGENTS.md) before changing the project and
[Architecture](ARCHITECTURE.md) for implementation boundaries. Follow
[Releasing](RELEASING.md) for tags; start adding changelog outcomes only after the
initial public `v0.1.0` release.


## Audit hygiene

Install the locked optional audit tools when performing a security/release review:

```bash
uv sync --locked --extra dev --group audit
uv run --no-sync zizmor --offline --persona pedantic --no-ignores --strict-collection .github/workflows
uv export --locked --extra dev --group audit --no-emit-project --output-file /tmp/odfa11y-audit.txt > /dev/null
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
