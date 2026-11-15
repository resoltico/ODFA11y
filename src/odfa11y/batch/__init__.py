# SPDX-License-Identifier: MPL-2.0
"""Explicit manifest-driven document workflows with durable progress evidence."""

from odfa11y.batch.batch_file import BatchItem, load_manifest
from odfa11y.batch.execute import run_batch
from odfa11y.batch.record import BatchRecord

__all__ = ["BatchItem", "BatchRecord", "load_manifest", "run_batch"]
