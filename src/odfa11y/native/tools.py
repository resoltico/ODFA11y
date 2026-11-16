# SPDX-License-Identifier: MPL-2.0
"""Selected tool identities, independent of PDF interpretation and application policy."""

from dataclasses import dataclass

from odfa11y.tool_identity import ToolIdentity
from odfa11y.tool_timeout import Timeout


@dataclass(frozen=True, slots=True)
class LibreOffice:
    executable: str
    identity: ToolIdentity


@dataclass(frozen=True, slots=True)
class VeraPdf:
    executable: str
    identity: ToolIdentity


@dataclass(frozen=True, slots=True)
class ResolvedTools:
    timeout: Timeout
    libreoffice: LibreOffice | None = None
    verapdf: VeraPdf | None = None
