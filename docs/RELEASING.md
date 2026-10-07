# Publication and releases

The initial public version will be **v0.1.0**. The package version is read from
`src/odfa11y/__init__.py`. Keep `CHANGELOG.md` unchanged until this first release
is publicly published; thereafter record notable net outcomes for subsequent
releases in its Unreleased section.

## Before creating the public repository

Review the intended initial commit, including hidden files. Keep private documents,
reports, environment files, credentials, virtual environments and generated build
outputs out of it. `.gitignore` prevents accidental staging of common local inputs;
it does not remove sensitive files already committed or deliberately force-added.
Run the required [development checks](DEVELOPING.md#required-checks), dependency
advisory review and redacted secret scan from [Audit hygiene](DEVELOPING.md#audit-hygiene).

Once the repository exists, enable GitHub private vulnerability reporting, secret
scanning/push protection where available, and branch rules requiring the Static analysis, Integration and
Linux, macOS and Windows Test checks. Restrict creation/modification of release tags to the maintainer.
These are repository settings, not promises that this source tree can enforce.
Do not add deployment or package-registry credentials just to enable GitHub releases.

The hosted checks must run successfully before release. Local success does not
establish GitHub runner behavior. Runtime dependencies and developer tools are
locked; external LibreOffice and runner image versions still vary.

## Prepare the version tag

After reviewing and committing the intended release, create an annotated tag that
exactly matches the package version. For the initial release:

```bash
git tag -a v0.1.0 -m 'ODFA11y v0.1.0'
git push origin v0.1.0
```

Do not move an already published version tag or replace its package assets. Prepare
a new version when public behavior or artifacts need to change.

## What the workflow does

The existing [Checks workflow](../.github/workflows/checks.yml) also handles version
tags, so release logic reuses the same gates:

1. Run policy, lint, type and boundary checks, tests (including real LibreOffice and
   veraPDF integration), known-dependency advisories, workflow security and
   a redacted history secret scan.
2. Build a wheel from the source archive and test its isolated installation.
3. Preserve the tested Linux wheel and source archive as an immutable workflow artifact.
4. Download those exact assets into the release job; do not rebuild after testing.
5. Verify tag/version, package metadata and bundled license with `tools/check_release.py`.
6. Extract the matching version section from the tagged checkout's `CHANGELOG.md`.
   Include its heading/date and retain all internal wording and Markdown; only outer
   whitespace is trimmed. Missing or duplicate version sections fail the release.
7. Create a **draft** GitHub release containing the wheel, source archive and those
   exact changelog notes. Unreleased and adjacent release sections are excluded.

A failed gate prevents the draft job. The release job alone gets the repository
write permission needed for its assets; it uses GitHub's scoped workflow token,
not a long-lived personal token. Version tags trigger this process; branch pushes,
PRs and manual check runs do not publish or create a draft release.

## Publish the reviewed draft

Review the assets and the changelog-derived notes, then publish the draft through
GitHub. The changelog in the tagged commit is the notes authority; the workflow
neither populates it nor generates separate prose from commit history. For the
initial v0.1.0, use its existing section without adding entries before publication.
After v0.1.0 is public, prepare each later release's section before tagging it.
If notes need correction, correct the changelog before tagging instead of maintaining
a second independently edited copy in GitHub.

No PyPI publication is configured. GitHub release assets can be installed locally,
for example with `python -m pip install /path/to/odfa11y-0.1.0-py3-none-any.whl` using
Python 3.14. A package-registry release can be added later with trusted publishing
when the registry project and publishing policy have been explicitly established.
