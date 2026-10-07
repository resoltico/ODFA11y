# SPDX-License-Identifier: MPL-2.0
"""Named assurance profiles: which stages a run requires and how strictly it gates."""

from __future__ import annotations

from dataclasses import dataclass

from odfa11y.errors import ConfigError

STAGE_NAMES = (
    "identify-source",
    "audit-source",
    "remediate",
    "audit-remediated",
    "export-source",
    "export-remediated",
    "audit-pdf",
    "verapdf",
    "fidelity",
)
INSPECT_STAGES = STAGE_NAMES[:4]
VERIFY_STAGES = tuple(name for name in STAGE_NAMES if name != "verapdf")


@dataclass(frozen=True, slots=True)
class Profile:
    """The gates a run enforces; the effective profile is recorded in the evidence."""

    name: str
    stages: tuple[str, ...]
    strict: bool
    verapdf_required: bool

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
    "inspect": Profile("inspect", INSPECT_STAGES, strict=False, verapdf_required=False),
    "verify": Profile("verify", VERIFY_STAGES, strict=False, verapdf_required=False),
    "production": Profile("production", STAGE_NAMES, strict=True, verapdf_required=True),
}
DEFAULT_PROFILE = "verify"


def profile_named(name: str) -> Profile:
    """Look up an assurance profile.

    Returns
    -------
    Profile
        The named profile.

    Raises
    ------
    ConfigError
        The name is not a known profile.

    """
    try:
        return PROFILES[name]
    except KeyError as exc:
        msg = f"Unknown profile {name!r}; use one of {', '.join(PROFILES)}"
        raise ConfigError(msg) from exc
