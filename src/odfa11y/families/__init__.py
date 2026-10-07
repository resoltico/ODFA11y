# SPDX-License-Identifier: MPL-2.0
"""The registry of document families: which adapter serves which kind of document."""

from .generic import GENERIC
from .registry import REGISTRY, adapter_for, config_tables

__all__ = ["GENERIC", "REGISTRY", "adapter_for", "config_tables"]
