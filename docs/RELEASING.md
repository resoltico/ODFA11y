# Publication and releases

The package version is declared once in `[project].version` in `pyproject.toml`. Record
notable net outcomes in the Unreleased section of `CHANGELOG.md` as work lands; at release,
retain Unreleased, move completed outcomes into a dated version section, and update the project version. Runtime
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
- Derive the repository description from `[project].description` in `pyproject.toml`;
  do not maintain a separate literal copy.
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
2. Build a wheel from the source archive and test its isolated installation. Restore the
   extracted source archive with `uv sync --locked` and run its contributor checks without
   importing modules from the original checkout or requiring `.git`.
3. Preserve the tested Linux wheel and source archive as an immutable workflow artifact.
4. Download those exact assets into the release job; do not rebuild after testing.
5. Derive the tag `v<version>` from the package and fail if that tag or any release (draft
   included) already exists. `tools.github_release absent` requires successful authenticated,
   paginated exact-state inspection; transport, authentication, server and parse failures
   abort rather than imply absence. Verify package metadata, licenses, schemas and the
   complete tracked contributor inventory with `tools/check_release.py` in a clean release checkout.
6. Extract the matching version section from the checked-out `CHANGELOG.md`.
   Include its heading/date and retain all internal wording and Markdown; only outer
   whitespace is trimmed. Missing or duplicate version sections fail the release.
7. Attest the build provenance of both distributions (`actions/attest-build-provenance`) and
   write `SHA256SUMS`.
8. Create a **draft** GitHub release containing the wheel, source archive, `SHA256SUMS` and those
   exact changelog notes, targeting the tested commit. The tag does not exist yet; GitHub creates it
   at that commit when the draft is published. Unreleased and adjacent release sections are excluded.
   Re-query the created draft, require the exact target SHA/notes/asset inventory, and
   download every asset to compare its bytes with the preserved tested files.

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

Publication requires separate maintainer authorization. The changelog in the tested
commit is the notes authority; the workflow does not generate prose from commit history.
Immediately before an authorized publication, recheck the draft with the preserved
artifacts, checksums and notes, substituting the tested full commit SHA:

```bash
uv run --no-sync python -m tools.github_release draft OWNER/REPO vVERSION \
  --target TESTED_COMMIT_SHA --directory /path/to/preserved-dist \
  --checksums /path/to/SHA256SUMS --notes /path/to/release-notes.md
```

Only after that succeeds and publication is authorized, publish through GitHub. Run the
same command with `published` afterwards: it requires the exact assets/notes and a
lightweight or peeled annotated tag pointing to the tested commit. A successful draft
verification does not establish publication; failed queries/downloads leave it unverified.

For a correction to an **unpublished** draft, first verify its draft status and target.
With explicit authorization, delete that draft and any unpublished tag created for it,
then commit the correction and rerun the full workflow. Its uniqueness gate deliberately
refuses existing drafts; a second run does not silently overwrite one. Do not edit notes
independently in GitHub or alter a published tag, release, asset or historical attribution.
Published corrections require a new version. Settings changes, draft deletion and public
publication each require corresponding authorization.

No PyPI publication is configured. GitHub release assets can be installed locally,
for example with `python -m pip install /path/to/odfa11y-VERSION-py3-none-any.whl` using
Python 3.14. A package-registry release can be added later with trusted publishing
when the registry project and publishing policy have been explicitly established.
