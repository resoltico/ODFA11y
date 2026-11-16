# SPDX-License-Identifier: MPL-2.0
"""status vocabulary."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import ClassVar, Literal, Protocol

from odfa11y.contracts import JsonProperty
from odfa11y.errors import Failure, InvalidOption, OdfA11yError
from odfa11y.exit_codes import EXIT_PRECEDENCE, ExitStatus, combine_statuses
from odfa11y.progress import Stage


def failure_status(error: BaseException) -> ExitStatus:
    """Classify an expected input error separately from execution failure.

    Returns
    -------
    ExitStatus
        Usage error for invalid arguments/plans, execution failure otherwise.

    """
    return ExitStatus(getattr(error, "exit_status", ExitStatus.EXECUTION_FAILURE))


class Profile(StrEnum):
    """The ordered assurance level selected for a run."""

    SOURCE = "source"
    PDF = "pdf"
    PRODUCTION = "production"

    @property
    def level(self) -> int:
        return tuple(type(self)).index(self)

    @property
    def strict(self) -> bool:
        return self is Profile.PRODUCTION

    @property
    def meaning(self) -> str:
        return {
            self.SOURCE: "Inspect and remediate the OpenDocument source without native export.",
            self.PDF: "Inspect source, native PDF export and fidelity without requiring veraPDF.",
            self.PRODUCTION: "Require PDF/UA validation and reject warnings as well as errors.",
        }[self]

    @classmethod
    def parse(cls, name: str) -> Profile:
        try:
            return cls(name)
        except ValueError as error:
            message = f"Unknown profile {name!r}; select source, pdf or production."
            raise InvalidOption(message) from error

    def __lt__(self, other: str) -> bool:
        if not isinstance(other, Profile):
            return NotImplemented
        return self.level < other.level

    def __le__(self, other: str) -> bool:
        if not isinstance(other, Profile):
            return NotImplemented
        return self.level <= other.level

    def __gt__(self, other: str) -> bool:
        if not isinstance(other, Profile):
            return NotImplemented
        return self.level > other.level

    def __ge__(self, other: str) -> bool:
        if not isinstance(other, Profile):
            return NotImplemented
        return self.level >= other.level


class GateReport(Protocol):
    """Measurements an outcome needs from its producer-owned report type."""

    @property
    def error_count(self) -> int: ...

    @property
    def warning_count(self) -> int: ...


def _gate_status(report: GateReport | None, strict: bool) -> ExitStatus:
    if report is not None and report.error_count:
        return ExitStatus.ERRORS
    if report is not None and strict and report.warning_count:
        return ExitStatus.STRICT_WARNINGS
    return ExitStatus.PASSED


@dataclass(frozen=True, slots=True)
class Passed[R: GateReport]:
    """The stage completed and supplied its declared artifacts."""

    report: R | None = None
    status: Literal["passed"] = field(default="passed", init=False)
    blocks_dependants: ClassVar[bool] = False

    def exit_status(self, strict: bool = False) -> ExitStatus:
        return ExitStatus.PASSED


@dataclass(frozen=True, slots=True)
class GateFailed[R: GateReport]:
    """The stage produced evidence containing findings rejected by the selected policy."""

    report: R
    status: Literal["gate-failed"] = field(default="gate-failed", init=False)
    blocks_dependants: ClassVar[bool] = False

    def exit_status(self, strict: bool = False) -> ExitStatus:
        return _gate_status(self.report, strict)


@dataclass(frozen=True, slots=True)
class Refused:
    """A source, plan or output policy prevented the stage from producing its artifact."""

    _error: OdfA11yError
    status: Literal["refused"] = field(default="refused", init=False)
    blocks_dependants: ClassVar[bool] = True

    @property
    def error(self) -> OdfA11yError:
        return self._error

    @JsonProperty
    def failure(self) -> Failure:
        return self._error.as_record()

    def exit_status(self, strict: bool = False) -> ExitStatus:
        return self.error.exit_status


@dataclass(frozen=True, slots=True)
class Crashed:
    """An execution or operating-system failure prevented the stage from completing."""

    _error: OdfA11yError
    status: Literal["crashed"] = field(default="crashed", init=False)
    blocks_dependants: ClassVar[bool] = True

    @property
    def error(self) -> OdfA11yError:
        return self._error

    @JsonProperty
    def failure(self) -> Failure:
        return self._error.as_record()

    def exit_status(self, strict: bool = False) -> ExitStatus:
        return ExitStatus.EXECUTION_FAILURE


class SkipReason(StrEnum):
    """Why the stage has no eligible invocation."""

    MISSING_INPUT = "missing-input"
    PROFILE = "profile"

    @property
    def meaning(self) -> str:
        return {
            self.MISSING_INPUT: "A preceding stage did not produce an input this stage requires.",
            self.PROFILE: "The selected profile does not require this stage.",
        }[self]


@dataclass(frozen=True, slots=True)
class Skipped:
    """The stage did not run because its required inputs or profile were absent."""

    reason: SkipReason
    stage: Stage | None = None
    status: Literal["skipped"] = field(default="skipped", init=False)
    blocks_dependants: ClassVar[bool] = True

    def exit_status(self, strict: bool = False) -> ExitStatus:
        return ExitStatus.PASSED


@dataclass(frozen=True, slots=True)
class NotApplicable:
    """The document family has no artifact or capability for this stage."""

    reason: str
    status: Literal["not-applicable"] = field(default="not-applicable", init=False)
    blocks_dependants: ClassVar[bool] = True

    def exit_status(self, strict: bool = False) -> ExitStatus:
        return ExitStatus.PASSED


type StageOutcome[R: GateReport] = (
    Passed[R] | GateFailed[R] | Refused | Crashed | Skipped | NotApplicable
)

__all__ = [
    "EXIT_PRECEDENCE",
    "Crashed",
    "ExitStatus",
    "GateFailed",
    "NotApplicable",
    "Passed",
    "Profile",
    "Refused",
    "SkipReason",
    "Skipped",
    "StageOutcome",
    "combine_statuses",
    "failure_status",
    "gate_outcome",
]


def gate_outcome[R: GateReport](report: R, *, strict: bool) -> Passed[R] | GateFailed[R]:
    """Classify report findings under the selected acceptance policy."""
    return GateFailed(report) if _gate_status(report, strict) else Passed(report)
