# SPDX-License-Identifier: MPL-2.0
"""Progress reaches interactive stderr before work and never changes evidence facts."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING, override

import pytest

from odfa11y.batch import run_batch
from odfa11y.cli.progress import progress_callback
from odfa11y.errors import OutputError
from odfa11y.outcomes import ProgressEvent, StepName, StepState
from odfa11y.pdf.fidelity import FidelityPolicy
from odfa11y.pipeline.context import RunSettings
from odfa11y.pipeline.engine import execute
from odfa11y.pipeline.profiles import profile_named
from tests.batch.test_batch import manifest_file
from tests.fixtures.plans import plan_header, reviewed_plan
from tests.fixtures.writer import make_minimal_odt

if TYPE_CHECKING:
    from pathlib import Path


class Terminal(io.StringIO):
    """A terminal stream with inspectable append-only output."""

    @override
    def isatty(self) -> bool:
        """Report an interactive stream.

        Returns
        -------
        bool
            True for terminal-only progress tests.

        """
        return True


class FailedTerminal(Terminal):
    """A disconnected terminal must not stop document processing."""

    @override
    def write(self, _text: str) -> int:
        """Fail every write.

        Raises
        ------
        OSError
            The terminal has disconnected.

        """
        msg = "Disconnected terminal"
        raise OSError(msg)


@pytest.mark.parametrize("output_format", ["json", "sarif"])
def test_machine_formats_never_get_progress(
    monkeypatch: pytest.MonkeyPatch, output_format: str
) -> None:
    terminal = Terminal()
    monkeypatch.setattr("sys.stderr", terminal)
    assert progress_callback(output_format) is None
    assert not terminal.getvalue()


def test_redirected_stderr_has_no_progress(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stderr", io.StringIO())
    assert progress_callback("text") is None


def test_progress_is_append_only_and_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    terminal = Terminal()
    monkeypatch.setattr("sys.stderr", terminal)
    callback = progress_callback("text")
    assert callback is not None
    callback(ProgressEvent(StepName.EXPORT_SOURCE, StepState.RUNNING))
    callback(ProgressEvent(StepName.EXPORT_SOURCE, StepState.PASSED))
    assert terminal.getvalue() == (
        "Progress: Export source PDF: running\nProgress: Export source PDF: passed\n"
    )


def test_pipeline_progress_precedes_work_and_publication(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "doc.odt")
    output = tmp_path / "evidence"
    events: list[tuple[str, str]] = []

    def observe(event: ProgressEvent) -> None:
        name, status = event.step, event.state
        if name == "identify-source" and status == "running":
            assert not output.exists()
        if name == "publish-evidence":
            assert output.exists() == (status == "passed")
        events.append((name, status))

    result = execute(
        source,
        reviewed_plan(source, (), FidelityPolicy()),
        output,
        RunSettings(profile=profile_named("source"), on_progress=observe),
    )
    assert events[0] == ("identify-source", "running")
    assert events[-2:] == [("publish-evidence", "running"), ("publish-evidence", "passed")]
    assert ("export-source", "running") not in events
    assert ("export-source", "skipped") in events
    assert "on_progress" not in result.as_dict()
    assert (output / "run.json").exists()


def test_failed_progress_stream_does_not_prevent_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = make_minimal_odt(tmp_path / "doc.odt")
    monkeypatch.setattr("sys.stderr", FailedTerminal())
    output = tmp_path / "evidence"
    execute(
        source,
        reviewed_plan(source, (), FidelityPolicy()),
        output,
        RunSettings(profile=profile_named("source"), on_progress=progress_callback("text")),
    )
    assert (output / "run.json").exists()


def test_batch_progress_contains_fixed_steps_and_published_status_only(tmp_path: Path) -> None:
    make_minimal_odt(tmp_path / "doc.odt")
    (tmp_path / "plan.toml").write_text(
        plan_header(tmp_path / "doc.odt")
        + '[decisions."document.metadata"]\ntitle="T"\nlanguage="en"'
    )
    manifest = manifest_file(tmp_path, [("one", "doc.odt", "plan.toml")])
    events: list[tuple[str, str]] = []
    record = run_batch(
        manifest,
        tmp_path / "batch",
        RunSettings(profile=profile_named("source")),
        on_progress=lambda event: events.append((event.step, event.state)),
    )
    assert events == [("batch-item", "running"), ("batch-item", "passed")]
    assert record.items[0].status == "completed"
    assert str(tmp_path) not in str(events)


def test_publication_failure_never_emits_passed_progress(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = make_minimal_odt(tmp_path / "doc.odt")
    events: list[tuple[str, str]] = []

    def unavailable_bundle(*_args: object, **_kwargs: object) -> dict[str, str]:
        msg = "Evidence storage unavailable"
        raise OSError(msg)

    monkeypatch.setattr("odfa11y.pipeline.publication.write_bundle", unavailable_bundle)
    with pytest.raises(OSError, match="storage unavailable"):
        execute(
            source,
            reviewed_plan(source, (), FidelityPolicy()),
            tmp_path / "evidence",
            RunSettings(
                profile=profile_named("source"),
                on_progress=lambda event: events.append((event.step, event.state)),
            ),
        )
    assert events[-2:] == [("publish-evidence", "running"), ("publish-evidence", "failed")]
    assert ("publish-evidence", "passed") not in events


def test_batch_interruption_emits_no_completion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    make_minimal_odt(tmp_path / "doc.odt")
    (tmp_path / "plan.toml").write_text(
        plan_header(tmp_path / "doc.odt")
        + '[decisions."document.metadata"]\ntitle="T"\nlanguage="en"'
    )
    manifest = manifest_file(tmp_path, [("one", "doc.odt", "plan.toml")])
    events: list[tuple[str, str]] = []

    def interrupted_pipeline(*_args: object, **_kwargs: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr("odfa11y.batch.run.execute", interrupted_pipeline)
    record = run_batch(
        manifest,
        tmp_path / "batch",
        RunSettings(profile=profile_named("source")),
        on_progress=lambda event: events.append((event.step, event.state)),
    )
    assert events == [("batch-item", "running"), ("batch-item", "failed")]
    assert record.exit_status == 3
    assert (tmp_path / "batch" / "batch.json").exists()


def test_observer_is_excluded_from_options_identity() -> None:
    plain = RunSettings(profile=profile_named("source"))
    observed = RunSettings(profile=profile_named("source"), on_progress=lambda _event: None)
    assert plain == observed
    assert repr(plain) == repr(observed)
    assert plain.profile == observed.profile


@pytest.mark.parametrize(
    ("failure", "status"),
    [(OutputError("Unsafe publication"), "failed"), (KeyboardInterrupt(), "failed")],
)
def test_publication_observes_domain_failure_and_interruption_without_replacing_exception(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: OutputError | KeyboardInterrupt,
    status: str,
) -> None:
    source = make_minimal_odt(tmp_path / "doc.odt")
    events: list[tuple[str, str]] = []

    def failed_bundle(*_args: object, **_kwargs: object) -> dict[str, str]:
        raise failure

    monkeypatch.setattr("odfa11y.pipeline.publication.write_bundle", failed_bundle)
    with pytest.raises(type(failure)) as caught:
        execute(
            source,
            reviewed_plan(source, (), FidelityPolicy()),
            tmp_path / "evidence",
            RunSettings(
                profile=profile_named("source"),
                on_progress=lambda event: events.append((event.step, event.state)),
            ),
        )
    assert caught.value is failure
    assert events[-2:] == [("publish-evidence", "running"), ("publish-evidence", status)]
    assert ("publish-evidence", "passed") not in events
