# SPDX-License-Identifier: MPL-2.0
"""remediate violations vocabulary."""

from enum import StrEnum


class ViolationKind(StrEnum):
    """Structured reasons a remediation candidate cannot be published."""

    FAILED_OUTCOME = "failed-outcome"
    PROTECTED_CONTENT = "protected-content"
    OPAQUE_RESOURCE = "opaque-resource"
    SCHEMA_REGRESSION = "schema-regression"
    EDIT_ACCOUNTING = "edit-accounting"
    FOREIGN_OPERATION = "foreign-operation"

    @property
    def meaning(self) -> str:
        """Return the core-owned meaning of this value."""
        return {
            self.FAILED_OUTCOME: "An edit did not establish its required postcondition.",
            self.PROTECTED_CONTENT: (
                "An edit changed content outside the allowed preservation contract."
            ),
            self.OPAQUE_RESOURCE: "An edit changed a payload that must remain opaque.",
            self.SCHEMA_REGRESSION: "An edit introduced an OpenDocument schema violation.",
            self.EDIT_ACCOUNTING: "An edit report disagrees with the observed XML changes.",
            self.FOREIGN_OPERATION: "An edit is unsupported by the selected document family.",
        }[self]
