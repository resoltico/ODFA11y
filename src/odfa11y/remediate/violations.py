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
