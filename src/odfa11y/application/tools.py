# SPDX-License-Identifier: MPL-2.0
"""One immutable selection of native executables and execution timeout."""

from dataclasses import dataclass
lazy from pathlib import Path

from odfa11y.application.native import NativeTools
from odfa11y.errors import Remedy, RemedyAction, ToolUnavailable
from odfa11y.native.libreoffice import require_supported_version
from odfa11y.native.tools import LibreOffice, ResolvedTools, VeraPdf
from odfa11y.tool_timeout import Timeout


@dataclass(frozen=True, slots=True)
class Tools:
    """The selected LibreOffice, veraPDF and per-native-call time limit."""

    soffice: str | Path | None = None
    verapdf: str | Path | None = None
    timeout: int | float = Timeout.DEFAULT

    def __post_init__(self) -> None:
        """Refuse unusable durations before any native work."""
        object.__setattr__(self, "timeout", Timeout(self.timeout))

    def resolve(
        self,
        *,
        libreoffice: bool = False,
        verapdf: bool = False,
        native_tools: NativeTools | None = None,
    ) -> ResolvedTools:
        """Resolve and identify only the tools required by the selected operation."""
        operations = native_tools or NativeTools()
        office = None
        validator = None
        if libreoffice:
            executable = operations.locate(self.soffice)
            identity = operations.identify(executable, timeout=self.timeout)
            require_supported_version(identity)
            office = LibreOffice(executable, identity)
        if verapdf:
            executable = operations.validator(self.verapdf)
            identity = operations.identify_validator(
                "veraPDF", executable, ("--version",), timeout=self.timeout
            )
            if not identity.version or identity.version == "unknown":
                message = "The selected veraPDF executable could not be identified."
                raise ToolUnavailable(message, remedy=Remedy(RemedyAction.INSTALL_TOOL, "veraPDF"))
            validator = VeraPdf(executable, identity)
        return ResolvedTools(Timeout(self.timeout), office, validator)
