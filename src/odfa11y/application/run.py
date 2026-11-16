# SPDX-License-Identifier: MPL-2.0
"""Prepare one captured, parsed run before creating user-visible output."""

import tempfile
from collections.abc import Callable
from contextlib import ExitStack
from pathlib import Path

from odfa11y.application.native import NativeTools
from odfa11y.application.tools import Tools
from odfa11y.capture import capture_source
from odfa11y.errors import InvalidOption, IoFailure
from odfa11y.evidence import require_free_directory
from odfa11y.families import require_spec
from odfa11y.native.tools import ResolvedTools
from odfa11y.odf import OdfDocument, Use
from odfa11y.plans import Plan
from odfa11y.progress import ProgressObserver, Step, step
from odfa11y.remediate.catalogue import load_plan
from odfa11y.remediate.compile import compile_decisions
from odfa11y.run.engine import execute
from odfa11y.run.record import RunRecord
from odfa11y.run.state import RunState
from odfa11y.status import Profile


def run(
    source: str | Path,
    plan: Plan | str | Path,
    output_dir: str | Path,
    *,
    tools: Tools | None = None,
    profile: Profile = Profile.PDF,
    observer: ProgressObserver | None = None,
    native_tools: NativeTools | None = None,
) -> RunRecord:
    """Validate preparation, then execute and publish an artifact-driven run."""
    if not isinstance(profile, Profile):
        message = "A run requires a Profile value."
        raise InvalidOption(message)
    operations = native_tools or NativeTools()
    selection = tools or Tools()
    return _run_with_tools(
        source,
        plan,
        output_dir,
        profile=profile,
        observer=observer,
        native_tools=operations,
        resolve_tools=lambda: selection.resolve(
            libreoffice=profile >= Profile.PDF,
            verapdf=profile is Profile.PRODUCTION,
            native_tools=operations,
        ),
    )


def _run_with_tools(
    source: str | Path,
    plan: Plan | str | Path,
    output_dir: str | Path,
    *,
    profile: Profile,
    observer: ProgressObserver | None,
    native_tools: NativeTools,
    resolve_tools: Callable[[], ResolvedTools],
) -> RunRecord:
    """Prepare each item in run order using its use case's shared tool resolution."""
    operations = native_tools
    target = Path(output_dir)
    try:
        with ExitStack() as lifetime, tempfile.TemporaryDirectory(prefix="odfa11y-run-") as scratch:
            work = Path(scratch)
            with step(observer, Step.PREPARE):
                selected = plan if isinstance(plan, Plan) else load_plan(plan)
                resolved = resolve_tools()
                require_free_directory(target)
                captured = lifetime.enter_context(capture_source(Path(source)))
                document = OdfDocument.open(captured.path)
                document.require(Use.AUDIT)
                family = require_spec(document.kind)
                decisions = compile_decisions(document, selected, source_sha256=captured.digest)
                state = RunState(
                    captured,
                    document,
                    selected,
                    decisions,
                    family,
                    resolved,
                    operations,
                    profile,
                    observer,
                    work,
                )
            return execute(state, target)
    except OSError as error:
        raise IoFailure.from_oserror(error) from error
