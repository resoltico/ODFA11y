# Current capability evidence

These records support the current [capability matrix](../CAPABILITIES.md) and
[accessibility boundaries](../ACCESSIBILITY.md):

- [doctor.json](doctor.json) identifies the application, libraries, platform and native
  tools, with a result for every registered capability probe.
- [text-exports.json](text-exports.json) binds the current Writer structure fixtures by
  SHA-256 and records PDF roles, built-in findings and independent validator outcomes.

Results apply to the recorded inputs and tool identities. They do not establish behavior
on other tool/platform combinations or replace document-level gates and human review.
Update a record only from an actual qualified run, then regenerate the capability reference.
The generator consumes these records without launching native tools.
