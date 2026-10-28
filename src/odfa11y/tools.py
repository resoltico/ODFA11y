# SPDX-License-Identifier: MPL-2.0
"""One immutable selection of native executables and execution timeout."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from odfa11y.native.export import DEFAULT_TIMEOUT_SECONDS
from odfa11y.native.process import validate_timeout

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True, slots=True)
class Tools:
    """The selected LibreOffice, veraPDF and per-native-call time limit."""

    soffice: str | Path | None = None
    verapdf: str | Path | None = None
    timeout: int | float = DEFAULT_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        """Refuse unusable durations before any native work."""
        validate_timeout(self.timeout)
