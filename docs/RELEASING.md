# Publication and releases

`[project].version` in [pyproject.toml](../pyproject.toml) is the package-version authority.
Runtime reporting derives installed distribution metadata. After changing the declaration,
run `uv lock` and `uv sync --locked` to refresh the lockfile/editable environment.
Record release outcomes in `CHANGELOG.md`; retain Unreleased and use a dated matching
version section for release notes.

## Repository settings

Source files describe required settings; they do not establish the live GitHub state.
Before release, verify:

- Private vulnerability reporting and secret scanning/push protection are enabled where
  available. Release-tag creation/modification is restricted to the maintainer, and
  *Immutable releases* protects published tags/assets.
- The GitHub environment named `release` has a required maintainer reviewer. The draft job
  uses this environment; it waits for review only when that protection is configured.
- The default branch requires exactly **CI gate**. This job waits for static analysis,
  platform Quality and Integration jobs and fails unless every required job succeeds,
  including rejection of skipped/cancelled results.
- The repository description agrees with `[project].description`, rather than a separate
  manually maintained description authority.

[.github/rulesets/default-branch.json](../.github/rulesets/default-branch.json) declares
the branch ruleset. Import it under *Settings → Rules → Rulesets → Import a ruleset*, or
use `gh api repos/OWNER/REPO/rulesets --input .github/rulesets/default-branch.json` when
authorized. A test checks its required check against the workflow gate. Other repository
protections still require direct inspection; this file does not configure release tags,
environments, immutable releases or private reporting.

GitHub release creation uses the scoped workflow token and needs no package-registry
credentials. Repository settings changes require corresponding authorization.

## Qualify the release inputs

Inspect intended files, including hidden paths, for private documents, reports, environment
files, credentials, virtual environments and build outputs. `.gitignore` limits accidental
staging; it does not sanitize committed content. Run [required development checks](DEVELOPING.md#required-checks)
and [audit hygiene scans](DEVELOPING.md#audit-hygiene), then require hosted checks on the
exact release commit. Local results do not establish hosted-platform behavior.

Dependency/tool constraints and the lockfile define Python inputs. Native installer pins,
checksums, runner selection and cache policy are declared in
[Checks](../.github/workflows/checks.yml). Some native/runner inputs follow their configured
current distributions; a Python lockfile does not freeze the complete toolchain.

## Start a release

Commit the intended package version and matching dated changelog section to `main`, wait
for its checks, then manually dispatch:

```bash
gh workflow run checks.yml --ref main -f release=true
```

The equivalent UI is *Actions → Checks → Run workflow*, selecting `main` and **release**.
Only manual dispatch on `main` with that input creates a draft. Pushes, tags, pull requests
and other manual runs run checks without starting a release.

## What the workflow does

The same [Checks workflow](../.github/workflows/checks.yml) qualifies and creates the draft:

1. Run static/security gates, per-platform tests and required real LibreOffice/veraPDF
   integration. **CI gate** requires all those job groups to succeed.
2. Build/inspect a source archive and wheel. Run the extracted source's contributor checks
   without `.git` or imports from the original checkout. Verify an isolated installed wheel
   with locked/hashed dependencies. Linux also requires byte-identical rebuilds.
3. Preserve the tested Linux distributions as a workflow artifact. The draft job downloads
   those exact assets and does not rebuild them.
4. Derive `v<version>` and require that neither that tag nor a matching release/draft exists.
   `tools.github_release absent` uses authenticated paginated exact-state queries;
   transport, authentication, server and parse failures abort rather than imply absence.
5. Validate package metadata, resources, notices and complete contributor inventory with
   `tools/check_release.py` in a clean release checkout. Extract exactly the matching
   changelog section, including its heading/date and internal Markdown. Missing/duplicate
   sections fail; Unreleased and adjacent sections are excluded.
6. Attest provenance for both distributions and write `SHA256SUMS`.
7. Create a draft targeting the tested full commit SHA with the exact notes, distributions
   and checksums. Re-query its identity and asset inventory, then download every asset and
   compare bytes with the preserved files. The verifier requires the tag to remain absent
   while the release is a draft.

The draft job requires **CI gate** and the configured `release` environment. It alone gets
repository-write and attestation permissions. Attestation failure must be resolved rather
than bypassed. CodeQL default setup and the scheduled Dependency audit are separate
repository/security controls; they are not additional jobs inside **CI gate**.

Consumers can verify downloaded assets with:

```bash
gh attestation verify FILE --repo resoltico/ODFA11y
sha256sum --check SHA256SUMS
```

Preserve the tested distributions, exact notes, checksums, commit identity and successful
workflow run so publication verification can use the same inputs.

## Publish the reviewed draft

Publication requires separate maintainer authorization. The matching changelog section in
the tested commit is the notes authority; commit history is not a release-note generator.
Immediately before authorized publication, substitute the tested full commit SHA and
preserved input paths:

```bash
uv run --no-sync python -m tools.github_release draft OWNER/REPO vVERSION \
  --target TESTED_COMMIT_SHA --directory /path/to/preserved-dist \
  --checksums /path/to/SHA256SUMS --notes /path/to/release-notes.md
```

After successful verification and authorization, publish through GitHub. Run the same
command with `published` afterwards. It requires exact assets/notes and a lightweight or
peeled annotated tag pointing to the tested commit. Draft verification alone does not
establish publication; query/download failure leaves the state unverified.

To correct an unpublished draft, verify its draft status and target first. With explicit
authorization, delete the draft and any unpublished tag created for it, commit the
correction and rerun full qualification. The uniqueness gate refuses existing drafts;
rerunning does not replace them. Do not edit notes independently in GitHub or change a
published tag, release or asset. Published corrections require a new version. Draft/tag
deletion and publication require corresponding authorization.

No PyPI publication is configured. A GitHub wheel asset can be installed with
`python -m pip install /path/to/odfa11y-VERSION-py3-none-any.whl` on a supported Python
interpreter. A package-registry workflow needs an explicitly established publishing policy.
