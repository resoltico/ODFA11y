# SPDX-License-Identifier: MPL-2.0
"""The registry of document families: which adapter serves which kind of document."""

from odfa11y.families.catalogue import REGISTRY, adapter_for
from odfa11y.families.generic import GENERIC

__all__ = ["GENERIC", "REGISTRY", "adapter_for"]
