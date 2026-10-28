# SPDX-License-Identifier: MPL-2.0
"""Writer default and effective language in all three script channels."""

from .defaults import default_language, set_default_language
from .effective import CHANNELS, effective_languages, language_location, language_nodes

__all__ = [
    "CHANNELS",
    "default_language",
    "effective_languages",
    "language_location",
    "language_nodes",
    "set_default_language",
]
