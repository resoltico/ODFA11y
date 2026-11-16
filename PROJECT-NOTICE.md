# ODFA11y licensing and source

Copyright © 2026 Ervins Strauhmanis. Contributors retain copyright in their contributions.

Original ODFA11y source, tests, tooling and accompanying documentation are licensed under the
GNU Affero General Public License, version 3 only (`AGPL-3.0-only`), unless separate terms are
identified for a file. See the unmodified license text in [LICENSE](LICENSE). You may copy,
modify and convey this work under those terms. It comes WITHOUT ANY WARRANTY, including the
implied warranties of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE; see sections 15–16.
Third-party components retain their own licenses and notices. This notice neither relicenses
third-party material nor grants exceptions to its terms.

Commercial use is permitted by the AGPL. Charging money, internal business use or offering a
SaaS service does not, by itself, require a paid license. Sections 4–6 govern conveyance of
covered source and object code. Under section 13, a modified version that supports remote
network interaction must prominently offer all users interacting with it an opportunity to
receive its Corresponding Source, without charge, through a standard means of copying software.
The required scope follows the license's definitions; it is not automatically every unrelated
system, service or item of business data. Read the license for the actual conditions.

## Source for a release

Each [GitHub release](https://github.com/resoltico/ODFA11y/releases) provides a tagged source
archive beside its distribution assets. The tagged repository contains preferred source,
`uv.lock`, build/install scripts, checks and setup instructions. Use the source archive for
the exact release you distribute; the Python package's smaller source distribution alone
omits contributor build and verification files. [Development](docs/DEVELOPING.md) describes
prerequisites and commands. Dependency sources and licenses remain available from their
upstream projects identified in [third-party notices](THIRD-PARTY-NOTICES.md).

A modifier or distributor must provide complete Corresponding Source for the actual covered
work and include any additional required source, build and installation inputs. An unchanged
upstream source archive does not satisfy obligations for modifications it omits. If a modified
version supports remote interaction, its source offer must meet section 13. Keep credentials,
private runtime configuration and customer documents out of source publications. The upstream
archive is a delivery aid, not a determination that every downstream deployment complies.

Upstream: https://github.com/resoltico/ODFA11y.
See [commercial licensing status](LICENSE-COMMERCIAL.md) for separate terms.

## Contribution terms

By submitting a contribution (code, documentation, tests or other material) to this
repository, you:

- confirm that you wrote it or otherwise have the right to submit it on these terms;
- license it to everyone under this repository's public license, `AGPL-3.0-only`; and
- also grant Ervins Strauhmanis a perpetual, worldwide, non-exclusive, royalty-free,
  irrevocable license to use, reproduce, modify, distribute and sublicense it, and to license
  it under other terms, including the commercial terms described in
  [LICENSE-COMMERCIAL.md](LICENSE-COMMERCIAL.md).

You keep the copyright in your contribution. Do not submit material you cannot license on
these terms; third-party components keep their own licenses. Each pull request confirms these
terms with the checkbox in its template. If your employer or another party controls rights
in the contribution, obtain their authorization before submitting it.
