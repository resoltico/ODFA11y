# Security

ODFA11y parses document containers, XML and PDF objects and can invoke LibreOffice
and veraPDF. It is alpha software. The maintainer is Ervins Strauhmanis; there is no
staffed response service or guaranteed response time.

## Reporting

Use **Security → Report a vulnerability** when GitHub private vulnerability
reporting is enabled. If that route is unavailable, open an issue asking the
maintainer for a private contact route without posting exploit details or sensitive
files. Supply a synthetic reproduction, affected revision and tool versions
through the private channel. Never send customer documents or credentials.

## Processing boundaries

XML entity resolution and network access are disabled. Document writes are validated
before replacement, and duplicate or unsafe ZIP member names cannot be rewritten.
These controls do not sandbox the parser, the pdfium renderer used for fidelity
comparison or external applications. Archives are loaded into memory after member-count/unpacked-size checks; hostile
documents can still exhaust process resources.

Process untrusted documents in an isolated environment with operating-system
resource limits and no sensitive files or credentials. Treat reports as potentially
sensitive: titles, text excerpts, image paths and diagnostic paths can appear in
them. Keep external applications current and inspect supported versions before
using production inputs.

The repository workflow checks known dependency advisories, secrets and workflow
security. A clean scan covers those checks and the advisory data available at the
time; it is not proof that the software has no vulnerabilities.
