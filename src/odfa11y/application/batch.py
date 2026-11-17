# SPDX-License-Identifier: AGPL-3.0-only
"""Batch application use case."""

from pathlib import Path

from odfa11y.application.io_errors import translate_io
from odfa11y.application.native import NativeTools
from odfa11y.application.run import _run_with_tools
from odfa11y.application.tools import Tools
from odfa11y.batch.execute import execute as execute_batch
from odfa11y.batch.record import BatchRecord
from odfa11y.errors import InvalidOption, IoFailure, OdfA11yError
from odfa11y.native.tools import ResolvedTools
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
    operations = native_tools or NativeTools()
    selection = tools or Tools()
    resolution: ResolvedTools | OdfA11yError | None = None

    def resolve_tools() -> ResolvedTools:
        nonlocal resolution
        if resolution is None:
            try:
                resolution = selection.resolve(
                    libreoffice=profile >= Profile.PDF,
                    verapdf=profile is Profile.PRODUCTION,
                    native_tools=operations,
                )
            except OdfA11yError as error:
                resolution = error
            except OSError as error:
                resolution = IoFailure.from_oserror(error)
        if isinstance(resolution, OdfA11yError):
            raise resolution.with_traceback(None)
        return resolution

    return execute_batch(
        batch_file,
        output_dir,
        profile=profile,
        runner=lambda source, plan, target, item_observer: _run_with_tools(
            source,
            plan,
            target,
            resolve_tools=resolve_tools,
            profile=profile,
            observer=item_observer,
            native_tools=operations,
        ),
        on_progress=observer,
    )
