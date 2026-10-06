# Contributing

Read [the development guide](../docs/DEVELOPING.md) for setup, required checks,
packaging and integration boundaries, and [AGENTS.md](../AGENTS.md) for change
and verification discipline.

For bug reports, describe the command, expected result, actual result and relevant
tool versions. Provide a small synthetic reproduction. Never upload customer
ODT/PDF files, private reports, credentials or identifiable production content.
Use [the security reporting route](SECURITY.md) for vulnerabilities.

Keep changes focused on a concrete requirement or reproduced defect. Include a
regression case that fails before the fix, inspect downstream effects, and report
which checks ran and which external tools or platforms were unavailable. Update
affected documentation. Begin recording release outcomes after the initial public
`v0.1.0` release; leave the changelog unchanged before then. A lint suppression needs a
central reason; a passing mock does not establish real application integration.
