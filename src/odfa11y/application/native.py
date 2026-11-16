# SPDX-License-Identifier: AGPL-3.0-only
"""The explicit native operations selected by an application use case."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from odfa11y.native.libreoffice import ExportSettings, export_pdfua, find_soffice, identify_soffice
from odfa11y.native.process import identify as identify_tool
from odfa11y.native.verapdf import Validator, find_verapdf, run_verapdf
from odfa11y.pdf.fidelity.compare import Rasterizer, render_pages
from odfa11y.tool_identity import ToolIdentity
from odfa11y.tool_timeout import Timeout


class ValidatorIdentity(Protocol):
    """Identify a selected veraPDF executable."""

    def __call__(
        self,
        name: str,
        executable: str,
        arguments: tuple[str, ...],
        /,
        *,
        timeout: float = Timeout.DEFAULT,
    ) -> ToolIdentity:
        """Return the identity measured from the executable."""
        ...


class OfficeIdentity(Protocol):
    """Identify the selected LibreOffice within the requested native-call duration."""

    def __call__(self, executable: str, /, *, timeout: float = Timeout.DEFAULT) -> ToolIdentity:
        """Return the executable's reported identity."""
        ...


type Exporter = Callable[[Path, Path, ExportSettings], Path]
type Locator = Callable[[str | Path | None], str]


@dataclass(frozen=True, slots=True)
class NativeTools:
    """Inject native behavior without replacing module attributes."""

    export: Exporter = export_pdfua
    validate: Validator = run_verapdf
    identify: OfficeIdentity = identify_soffice
    render: Rasterizer = render_pages
    locate: Locator = find_soffice
    validator: Locator = find_verapdf
    identify_validator: ValidatorIdentity = identify_tool
