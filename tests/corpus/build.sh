#!/bin/sh
# Regenerate the corpus documents from sources/ with a real LibreOffice Writer.
#
# Usage: sh tests/corpus/build.sh        (from the repository root; needs `soffice` on PATH)
#
# Writer imports each source and saves it as a package (.odt), and some also as flat XML (.fodt).
# The output embeds timestamps, so it differs on every run: after regenerating, review the
# changes and update the hashes in manifest.toml (see docs/DEVELOPING.md).
set -eu

uv run --no-sync odfa11y doctor --format json >/dev/null

corpus=$(cd "$(dirname "$0")" && pwd)
profile=$(mktemp -d)
trap 'rm -rf "$profile"' EXIT

writer() {
  soffice --headless "-env:UserInstallation=file://$profile" "$@" >/dev/null
}

for source in "$corpus"/sources/*.html; do
  writer --infilter="HTML (StarWriter)" --convert-to odt:writer8 --outdir "$corpus" "$source"
done
for source in "$corpus"/sources/*.fodt; do
  writer --convert-to odt:writer8 --outdir "$corpus" "$source"
done
# Only these documents also exist as flat XML; each pair must audit identically.
for name in footnotes header-footer images-undescribed links table-merged-cells; do
  writer --convert-to "fodt:OpenDocument Text Flat XML" --outdir "$corpus" "$corpus/$name.odt"
done
soffice --version
