# SPDX-License-Identifier: MPL-2.0
"""Convenient public use-case invocations for workflow fixtures."""

from dataclasses import dataclass, field

from odfa11y.application import batch as application_batch
from odfa11y.application import run
from odfa11y.application.tools import Tools
from odfa11y.progress import ProgressObserver
from odfa11y.run.stages import STAGES
from odfa11y.status import Profile

STAGE_NAMES = tuple(spec.name for spec in STAGES)


@dataclass(frozen=True, slots=True)
class RunSettings:
    tools: Tools = field(default_factory=Tools)
    profile: Profile = Profile.PDF
    on_progress: ProgressObserver | None = field(default=None, repr=False, compare=False)


def execute(source, plan, target, options=None, *, native_tools=None):
    selected = options or RunSettings()
    return run(
        source,
        plan,
        target,
        tools=selected.tools,
        profile=selected.profile,
        observer=selected.on_progress,
        native_tools=native_tools,
    )


def run_batch(manifest, target, options=None, *, on_progress=None, native_tools=None):
    selected = options or RunSettings()
    return application_batch(
        manifest,
        target,
        tools=selected.tools,
        profile=selected.profile,
        observer=on_progress or selected.on_progress,
        native_tools=native_tools,
    )


def stage_statuses(record):
    return {stage.name: stage.outcome.status for stage in record.stages}
