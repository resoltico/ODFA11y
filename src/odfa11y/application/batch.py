# SPDX-License-Identifier: MPL-2.0
"""Batch application use case."""

from pathlib import Path

from odfa11y.application.io_errors import translate_io
from odfa11y.application.native import NativeTools
from odfa11y.application.run import run
from odfa11y.application.tools import Tools
from odfa11y.batch.execute import execute as execute_batch
from odfa11y.batch.record import BatchRecord
from odfa11y.errors import InvalidOption
from odfa11y.progress import ProgressObserver
from odfa11y.status import Profile


@translate_io
def batch(
    batch_file: str | Path,
    output_dir: str | Path,
    *,
    tools: Tools | None = None,
    profile: Profile = Profile.PDF,
    observer: ProgressObserver | None = None,
    native_tools: NativeTools | None = None,
) -> BatchRecord:
    """Execute independent batch-file items and retain their actual outcomes."""
    if not isinstance(profile, Profile):
        message = "A batch requires a Profile value."
        raise InvalidOption(message)
    return execute_batch(
        batch_file,
        output_dir,
        profile=profile,
        runner=lambda source, plan, target, item_observer: run(
            source,
            plan,
            target,
            tools=tools,
            profile=profile,
            observer=item_observer,
            native_tools=native_tools,
        ),
        on_progress=observer,
    )
