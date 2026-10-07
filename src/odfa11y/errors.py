# SPDX-License-Identifier: MPL-2.0
"""Domain exceptions: every expected failure is one of these, never a bare builtin."""

from __future__ import annotations


class OdfA11yError(Exception):
    """Base class for failures the command line reports without a traceback."""


class PackageError(OdfA11yError):
    """An ODF package or flat document is unreadable, corrupt or unsafe."""


class MissingMemberError(PackageError):
    """A required package member does not exist."""


class XmlParseError(PackageError):
    """A package member contains malformed XML."""


class ConfigError(OdfA11yError):
    """The configuration file is malformed or contains unsupported values."""


class RemediationError(OdfA11yError):
    """A remediation run failed a precondition or postcondition and wrote nothing."""


class OutputError(OdfA11yError):
    """An output destination is unsafe or already occupied."""


class UnsupportedKindError(OdfA11yError):
    """The requested operation does not exist for this kind of document."""


class ToolError(OdfA11yError):
    """An external application could not provide what was asked of it.

    ``details`` holds bounded diagnostic output (for example a failed tool's stderr) for a
    person at a terminal; ``str(error)`` stays short and free of local paths.
    """

    def __init__(self, message: str, *, details: str = "") -> None:
        """Keep the diagnostic output apart from the message."""
        super().__init__(message)
        self.details = details


class ToolNotFoundError(ToolError):
    """An external application is not installed or not at the given path."""


class ToolFailedError(ToolError):
    """An external application failed, timed out or produced unusable output."""
