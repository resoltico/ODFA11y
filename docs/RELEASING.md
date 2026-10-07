# Publication and releases

The package version is declared once in `[project].version` in `pyproject.toml`. Record
notable net outcomes in the Unreleased section of `CHANGELOG.md` as work lands; at release,
rename that section to the new version and date and update the project version. Runtime
reporting reads installed distribution metadata. After changing the version in a checkout,
run `uv lock` and `uv sync --locked` to refresh the lockfile and editable installation.

## Repository settings

These are GitHub settings, not promises this source tree can enforce:

- Enable private vulnerability reporting and secret scanning/push protection where
  available. Restrict creation and modification of release tags to the maintainer, and enable
  *Immutable releases* so a published release's tag and assets can no longer change.
- Create a GitHub environment named `release` and add the maintainer as a required reviewer;
  the draft job waits for that approval.
- Require exactly one status check, **`CI gate`**, on the default branch. The gate is a
  final job that waits for the static, per-OS test and integration jobs and fails unless
  every one succeeded (a skipped or cancelled job fails it), so jobs can be added or
  renamed without touching the setting. [`.github/rulesets/default-branch.json`](../.github/rulesets/default-branch.json)
  holds the ruleset as code: import it under *Settings → Rules → Rulesets → Import a
  ruleset* (or `gh api repos/OWNER/REPO/rulesets --input .github/rulesets/default-branch.json`),
  then remove any older protection that requires individual job checks. A test keeps the
  ruleset and the workflow's gate name in agreement.
- Set the repository description to: `Recognise and check every OpenDocument kind; audit,
  remediate and export text documents and spreadsheets as PDF/UA with evidence.` Keep it in agreement with
  `description` in `pyproject.toml`.
- Do not add deployment or package-registry credentials just to enable GitHub releases.

Review the intended release, including hidden files: keep private documents, reports,
environment files, credentials, virtual environments and build outputs out of it.
`.gitignore` prevents accidental staging of common local inputs; it does not remove
sensitive files already committed. Run the [development checks](DEVELOPING.md#required-checks)
and the [audit hygiene](DEVELOPING.md#audit-hygiene) scans before tagging. Hosted checks
must pass; local success does not establish GitHub runner behavior. Runtime dependencies
and developer tools are locked. LibreOffice 26.8 is the minimum; the Linux/Windows installers and
veraPDF are checksum-pinned, while macOS LibreOffice and runner images may vary.

## Start a release

Releases are started by hand and never by pushing a tag. Commit the version in
`pyproject.toml` and the dated changelog section to the default branch, wait for its
checks, then start the workflow on that branch:

```bash
gh workflow run checks.yml --ref main -f release=true
```

or use *Actions → Checks → Run workflow* with **release** ticked. The run only creates a
release from `main`; on any other ref the release job is skipped. Do not move a published
tag or replace its assets; prepare a new version instead.

## What the workflow does

The [Checks workflow](../.github/workflows/checks.yml) also creates the draft release, so
release logic reuses the same gates on the same commit:

1. Run policy, lint, type and boundary checks, tests (including real LibreOffice and
   veraPDF integration), known-dependency advisories, workflow security and a redacted
   history secret scan; the `CI gate` job summarises them.
2. Build a wheel from the source archive and test its isolated installation.
3. Preserve the tested Linux wheel and source archive as an immutable workflow artifact.
4. Download those exact assets into the release job; do not rebuild after testing.
5. Derive the tag `v<version>` from the package and fail if that tag or any release (draft
   included) already exists. Verify package metadata and bundled license with
   `tools/check_release.py`.
6. Extract the matching version section from the checked-out `CHANGELOG.md`.
   Include its heading/date and retain all internal wording and Markdown; only outer
   whitespace is trimmed. Missing or duplicate version sections fail the release.
7. Attest the build provenance of both distributions (`actions/attest-build-provenance`) and
   write `SHA256SUMS`.
8. Create a **draft** GitHub release containing the wheel, source archive, `SHA256SUMS` and those
   exact changelog notes, targeting the tested commit. The tag does not exist yet; GitHub creates it
   at that commit when the draft is published. Unreleased and adjacent release sections are excluded.

CI also rebuilds the distributions and requires byte-identical results, so the assets can be
reproduced from the released source with `uv build`. Consumers can verify a downloaded asset with
`gh attestation verify FILE --repo resoltico/odfa11y` and `sha256sum --check SHA256SUMS`.
Provenance attestations require a repository that supports them; if the draft job fails at that
step, fix the repository setting rather than removing the step.

A weekly `Dependency audit` workflow re-checks the locked dependencies against advisories
between pushes. Enable GitHub's CodeQL default setup in the repository settings for code scanning;
no workflow file is needed.

A failed `CI gate` prevents the draft job. The release job alone gets the repository
write and attestation permissions it needs; it uses GitHub's scoped workflow token,
not a long-lived personal token. Only a manual run of the workflow on `main` with
**release** ticked creates a draft; pushes, PRs, tags and other manual runs do not.

## Publish the reviewed draft

Review the assets and the changelog-derived notes, then publish the draft through
GitHub. The changelog in the released commit is the notes authority; the workflow
neither populates it nor generates separate prose from commit history. Prepare each
release's section before starting the release. If notes need correction, correct the changelog and start a new run instead of maintaining
a second independently edited copy in GitHub.

No PyPI publication is configured. GitHub release assets can be installed locally,
for example with `python -m pip install /path/to/odfa11y-VERSION-py3-none-any.whl` using
Python 3.14. A package-registry release can be added later with trusted publishing
when the registry project and publishing policy have been explicitly established.
