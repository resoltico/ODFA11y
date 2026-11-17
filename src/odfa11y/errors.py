# SPDX-License-Identifier: AGPL-3.0-only
"""Expected failures declare their code, exit status and actionable remedy."""

from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Literal

from odfa11y.exit_codes import ExitStatus


class RemedyAction(StrEnum):
    """Actions a caller can present to recover from a refused operation."""

    REGENERATE_PLAN = "regenerate-plan"
    REBIND_PLAN = "rebind-plan"
    CHOOSE_OUTPUT = "choose-output"
    INSTALL_TOOL = "install-tool"
    EDIT_IN_APPLICATION = "edit-in-application"
    EMBED_RESOURCE = "embed-resource"

    @property
    def meaning(self) -> str:
        return {
            self.REGENERATE_PLAN: "Generate a fresh plan for the source and review its answers.",
            self.REBIND_PLAN: "Create a newly bound plan and review answers that no longer match.",
            self.CHOOSE_OUTPUT: "Choose an available output destination.",
            self.INSTALL_TOOL: "Install or select the required native tool.",
            self.EDIT_IN_APPLICATION: "Edit the named target in its authoring application.",
            self.EMBED_RESOURCE: "Embed the named rendering resource in the source document.",
        }[self]


@dataclass(frozen=True, slots=True)
class Remedy:
    """A producer-owned next action, independent of presentation wording."""

    action: RemedyAction
    target: str | None = None
    detail: str | None = None


DIAGNOSTIC_CHARACTERS = 4096


type FailureStatus = Literal[
    ExitStatus.ERRORS, ExitStatus.EXECUTION_FAILURE, ExitStatus.USAGE_ERROR
]


@dataclass(frozen=True, slots=True)
class Failure:
    """The immutable public facts of an expected failure."""

    code: str
    message: str
    exit_status: FailureStatus
    remedy: Remedy | None = None
    problems: tuple[str, ...] = ()
    details: str = ""


class OdfA11yError(Exception):
    """An expected failure that every application boundary can report."""

    code: ClassVar[str] = "execution-failure"
    exit_status: ClassVar[FailureStatus] = ExitStatus.EXECUTION_FAILURE
    default_remedy: ClassVar[Remedy | None] = None

    def __init__(
        self,
        message: str,
        *,
        remedy: Remedy | None = None,
        details: str = "",
        problems: tuple[str, ...] = (),
    ) -> None:
        self.message = message[:DIAGNOSTIC_CHARACTERS]
        self.problems = tuple(problem[:DIAGNOSTIC_CHARACTERS] for problem in problems)
        super().__init__(self.message + ("\n" + "\n".join(self.problems) if self.problems else ""))
        self.remedy = remedy if remedy is not None else self.default_remedy
        self.details = details[:DIAGNOSTIC_CHARACTERS]

    def as_record(self) -> Failure:
        return Failure(
            self.code, self.message, self.exit_status, self.remedy, self.problems, self.details
        )


class InvalidOption(OdfA11yError):
    """Options do not describe a supported invocation."""

    code = "invalid-option"
    exit_status = ExitStatus.USAGE_ERROR


class PlanError(OdfA11yError):
    """The plan is malformed, unsupported or no longer bound to the source."""

    code = "invalid-plan"
    exit_status = ExitStatus.USAGE_ERROR
    default_remedy = Remedy(RemedyAction.REGENERATE_PLAN)


class OutputOccupied(OdfA11yError):
    """The requested destination cannot be safely published."""

    code = "output-occupied"
    exit_status = ExitStatus.USAGE_ERROR
    default_remedy = Remedy(RemedyAction.CHOOSE_OUTPUT)


class DocumentRefusal(OdfA11yError):
    """The source does not support the requested operation safely."""

    code = "document-refused"
    exit_status = ExitStatus.ERRORS


class PackageError(DocumentRefusal):
    """An ODF container is unreadable, corrupt or unsafe."""

    code = "invalid-package"


class MissingMemberError(PackageError):
    """A required package member is absent."""

    code = "missing-member"


class XmlParseError(PackageError):
    """A required package member contains malformed XML."""

    code = "invalid-xml"


class ToolUnavailable(OdfA11yError):
    """A required native application cannot be found or identified."""

    code = "tool-unavailable"
    exit_status = ExitStatus.EXECUTION_FAILURE
    default_remedy = Remedy(RemedyAction.INSTALL_TOOL)


class ToolFailure(OdfA11yError):
    """A native application failed, timed out or produced unusable output."""

    code = "tool-failed"
    exit_status = ExitStatus.EXECUTION_FAILURE


class IoFailure(OdfA11yError):
    """An operating-system error occurred at a file-system boundary."""

    code = "io-failure"
    exit_status = ExitStatus.EXECUTION_FAILURE

    @classmethod
    def from_oserror(cls, error: OSError) -> IoFailure:
        reason = error.strerror or str(error) or "operating-system error"
        return cls(f"{type(error).__name__}: {reason}")
