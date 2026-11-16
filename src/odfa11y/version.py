# SPDX-License-Identifier: AGPL-3.0-only
"""Read the installed distribution version without importing application workflows."""

from importlib.metadata import version

__version__ = version("odfa11y")
