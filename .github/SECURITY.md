# Security

ODFA11y parses document containers, XML and PDF objects and can invoke LibreOffice and
veraPDF. Its [project metadata](../pyproject.toml) declares alpha status and the maintainer.
There is no staffed response service or guaranteed response time.

## Reporting

Use **Security → Report a vulnerability** when GitHub private vulnerability reporting is
enabled. If unavailable, open an issue requesting a private contact route without posting
exploit details or sensitive files. Supply a synthetic reproduction, affected revision
and tool versions through the private channel. Never send customer documents or credentials.

## Processing boundaries

The XML parser disables entity resolution and network access. Native importers do not
inherit that network restriction. Package/XML/PDF limits, guarded source decisions and
atomic writes reduce specific risks; they do not sandbox parsers, pdfium, LibreOffice or
veraPDF, and they do not impose a process CPU/memory limit. Hostile inputs can exhaust
resources. See [scope and threat model](../docs/ACCESSIBILITY.md#threat-model).

Guarded native operations refuse recognized unsupported rendering/resource declarations
and incorrect file/object addressing. Captured pipeline exports also refuse
location-sensitive fields. These are bounded declaration/context controls, not universal
network isolation or inspection of opaque embedded internals. The low-level native export
API requires caller policy and isolation. `production` selects assurance gates; it does
not provide an isolated execution environment.

Pipeline capture checks bounded regular-file identity. Source/staging ancestor namespaces
must remain stable; leaf identity does not prevent parent exchanges or concurrent in-place
writes. Bundle verification likewise requires stable directory namespaces. See
[Evidence](../docs/EVIDENCE.md#no-local-paths) for privacy and capture/verification details.

Process untrusted documents under operating-system isolation/resource limits, without
sensitive files or credentials. Keep native applications current within the supported
toolchain. Reports can contain titles, text excerpts and authored references; bundles
include document payloads. Diagnostic path redaction does not make documents public-safe.

Repository checks cover configured dependency advisories, secrets and workflow security.
A passing scan establishes those checks against the available advisory data, not absence
of vulnerabilities. Follow [audit hygiene](../docs/DEVELOPING.md#audit-hygiene) for review.
