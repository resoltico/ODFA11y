# SPDX-License-Identifier: MPL-2.0
"""Named assurance profiles: which stages a run requires and how strictly it gates."""

from __future__ import annotations

from dataclasses import dataclass

from odfa11y.errors import PlanError
from odfa11y.outcomes import PIPELINE_STAGES, StageName

SOURCE_STAGES = PIPELINE_STAGES[:4]
VERIFY_STAGES = tuple(name for name in PIPELINE_STAGES if name != StageName.VALIDATE_PDF)


@dataclass(frozen=True, slots=True)
class Profile:
    """The gates a run enforces; the effective profile is recorded in the evidence."""

    name: str
    stages: tuple[StageName, ...]
    strict: bool
    verapdf_required: bool

    def __str__(self) -> str:
        """Display the profile's command-line name.

        Returns
        -------
        str
            The selected profile name.

        """
        return self.name

    def as_dict(self) -> dict[str, object]:
        """Serialize the profile.

        Returns
        -------
        dict[str, object]
            The name, the stages it runs and its strictness.

        """
        return {
            "name": self.name,
            "stages": list(self.stages),
            "strict": self.strict,
            "verapdf_required": self.verapdf_required,
        }


PROFILES = {
    "source": Profile("source", SOURCE_STAGES, strict=False, verapdf_required=False),
    "verify": Profile("verify", VERIFY_STAGES, strict=False, verapdf_required=False),
    "production": Profile("production", PIPELINE_STAGES, strict=True, verapdf_required=True),
}
DEFAULT_PROFILE = PROFILES["verify"]


def profile_named(name: str) -> Profile:
    """Look up an assurance profile.

    Returns
    -------
    Profile
        The named profile.

    Raises
    ------
    PlanError
        The name is not a known profile.

    """
    try:
        return PROFILES[name]
    except KeyError as exc:
        msg = f"Unknown profile {name!r}; use one of {', '.join(PROFILES)}"
        raise PlanError(msg) from exc
