# Native reproductions

`text-contexts.fodt` is invented source for the current-flow/revision regression.
It contains a main heading, stored deletion history, a note, annotation, conditional
section, authored link/bookmark/field and ODF space/tab/line-break separators. Its source
is authored test data; no customer document or actual person's information is included.

`text-contexts.odt` was written from that source with LibreOffice 26.8.1.1 on macOS
on 2026-10-14. Reproduce with an isolated profile:

```sh
soffice -env:UserInstallation=file:///absolute/private/profile --headless \
  --convert-to odt --outdir /absolute/output tests/reproductions/text-contexts.fodt
```

The native producer output has existing bundled-schema violations (nine diagnostics in
the original production environment). Tests compare the actual before/after schema result,
protect excluded XML exactly, and check actual rendered word boundaries. Native output
is evidence of producer behavior, not proof of ODF conformance. `unnamed-link.odt` retains
its existing independent Writer PDF alternate-description failure regression.
