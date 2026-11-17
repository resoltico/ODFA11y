# SPDX-License-Identifier: AGPL-3.0-only
"""Progress carries item identity and signal policy belongs only to the CLI."""

import signal
from pathlib import Path

import pytest

from odfa11y import audit
from odfa11y import batch as execute_batch
from odfa11y.progress import Step, StepState, step
from odfa11y.status import Profile
from tests.batch.test_batch import write_batch_file
from tests.fixtures.plans import plan_header
from tests.fixtures.writer import make_minimal_odt


def test_step_emits_running_and_terminal_state_with_item_identity() -> None:
    events = []
    with step(events.append, Step.PREPARE, item="one"):
        pass
    assert [(event.state, event.item) for event in events] == [
        (StepState.RUNNING, "one"),
        (StepState.PASSED, "one"),
    ]


def test_interruption_is_observed_and_propagated() -> None:
    events = []
    with pytest.raises(KeyboardInterrupt), step(events.append, Step.REMEDIATE, item="two"):
        raise KeyboardInterrupt
    assert [(event.state, event.item) for event in events] == [
        (StepState.RUNNING, "two"),
        (StepState.FAILED, "two"),
    ]


def test_library_operations_leave_signal_handlers_untouched_and_batch_events_identified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*_args, **_kwargs):
        pytest.fail("A library operation changed a process signal handler")

    monkeypatch.setattr(signal, "signal", forbidden)
    source = make_minimal_odt(tmp_path / "source.odt")
    assert audit(source).exit_status == 0
    (tmp_path / "plan.toml").write_text(plan_header(source))
    batch = write_batch_file(
        tmp_path, [("one", "source.odt", "plan.toml"), ("two", "source.odt", "plan.toml")]
    )
    events = []
    result = execute_batch(
        batch, tmp_path / "output", profile=Profile.parse("source"), observer=events.append
    )
    assert result.exit_status == 0
    assert events
    assert {event.item for event in events} == {"one", "two"}
