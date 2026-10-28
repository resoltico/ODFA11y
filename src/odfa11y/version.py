# SPDX-License-Identifier: MPL-2.0
"""Read the installed distribution version without importing application workflows."""

from importlib.metadata import version

__version__ = version("odfa11y")
