# SPDX-License-Identifier: MPL-2.0
"""The contract between the ODF core and the document families that plug into it."""

from . import config_tables
from .family import FamilyAdapter, ReviewItem
from .operation import Operation, Outcome, Status

__all__ = ["FamilyAdapter", "Operation", "Outcome", "ReviewItem", "Status", "config_tables"]
