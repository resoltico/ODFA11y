# SPDX-License-Identifier: MPL-2.0
"""Help and next actions preserve reviewed plans and remain safe to copy."""

from __future__ import annotations

import argparse
import shlex
import tomllib
from pathlib import Path

import pytest

from odfa11y.audit import audit_odf, render_template
from odfa11y.cli import main
from odfa11y.cli.guidance import audit_next_step, error_hint
from odfa11y.cli.parser import build_parser
from odfa11y.errors import OutputError, PlanError, ToolNotFoundError
from odfa11y.families.text import ADAPTER
from odfa11y.report import Report, rules

from .fixtures import make_minimal_odt


@pytest.mark.parametrize(
    "name",
    [
        "audit",
        "template",
        "remediate",
        "export",
        "compare",
        "pipeline",
        "batch",
        "styles",
        "check-evidence",
        "doctor",
    ],
)
def test_every_command_help_has_examples_accepted_by_its_parser(
    name: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as raised:
        main([name, "--help"])
    assert raised.value.code == 0
    captured = capsys.readouterr()
    assert not captured.err
    help_text = captured.out
    assert "Examples:" in help_text
    assert "\x1b" not in help_text
    examples = help_text.split("Examples:", 1)[1].replace("\\\n", "").splitlines()
    seen = 0
    for line in examples:
        words = shlex.split(line, comments=True)
        if not words or words[0] != "odfa11y":
            continue
        if ">" in words:
            words = words[: words.index(">")]
        build_parser().parse_args(words[1:])
        seen += 1
    assert seen > 0, name


def test_bare_invocation_shows_workflow_without_executing(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as raised:
        main([])
    assert raised.value.code == 4
    captured = capsys.readouterr()
    assert not captured.out
    assert "Workflow" in captured.err
    assert "Exit statuses" in captured.err
    assert not list(tmp_path.iterdir())


def test_command_typo_suggests_without_executing(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["audti", "absent.odt"])
    assert raised.value.code == 4
    captured = capsys.readouterr()
    assert "maybe you meant 'audit'" in captured.err
    assert not captured.out


def test_next_command_handles_shell_names_and_leading_dash() -> None:
    source = Path("-a document; $(touch unwanted).odt")
    report = Report(kind="odf", subject=source.name, sources=(source,))
    report.add(rules.META001)
    hint = audit_next_step(argparse.Namespace(format="text"), [report])
    assert hint is not None
    command = hint.splitlines()[0].removeprefix("Next: ")
    assert shlex.split(command) == ["odfa11y", "template", "--", str(source)]
    assert build_parser().parse_args(shlex.split(command)[1:]).source == source


@pytest.mark.parametrize(("kind", "source"), [("pdf", "a.pdf"), ("odf", "a\n.odt")])
def test_no_invalid_or_unfaithful_copyable_next_commands(kind: str, source: str) -> None:
    report = Report(kind=kind, subject=source, sources=(Path(source),))
    report.add(rules.META001)
    assert audit_next_step(argparse.Namespace(format="text"), [report]) is None
    assert audit_next_step(argparse.Namespace(format="json"), [report]) is None


def test_unreadable_document_does_not_offer_template() -> None:
    report = Report(kind="odf", subject="bad.odt", sources=(Path("bad.odt"),))
    report.add(rules.META001)
    report.add(rules.PKG000)
    assert audit_next_step(argparse.Namespace(format="text"), [report]) is None


def test_template_header_escapes_untrusted_subject_without_active_toml(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "doc.odt", features={"with_image_without_alt": True})
    report = audit_odf(source)
    report.subject = "doc\n[document]\ntitle='Injected'\x1b[2J\u202e.odt"
    template = render_template(report, ADAPTER)
    assert tomllib.loads(template) == {}
    assert "\x1b" not in template
    assert "\u202e" not in template
    assert "# with the reviewed configuration" in template
    assert "fingerprint" in template


def test_recovery_preserves_configuration_and_existing_output() -> None:
    args = argparse.Namespace(command="remediate", config=Path("reviewed.toml"))
    assert "edit the existing configuration" in (error_hint(args, PlanError("wrong type")) or "")
    assert "preserve" in (error_hint(args, OutputError("occupied")) or "")
    assert error_hint(args, ValueError("unexpected")) is None


def test_tool_recovery_matches_available_command_options(
    capsys: pytest.CaptureFixture[str],
) -> None:
    for command, flag in [("audit", "--verapdf-path"), ("export", "--soffice")]:
        hint = error_hint(argparse.Namespace(command=command), ToolNotFoundError("missing"))
        assert hint is not None
        assert flag in hint
        with pytest.raises(SystemExit) as raised:
            main([command, "--help"])
        assert raised.value.code == 0
        assert flag in capsys.readouterr().out


@pytest.mark.parametrize(
    "arguments",
    [
        ["audit\u202e"],
        ["audit", "absent.odt", "--hostile\x1b[2J\nInjected"],
        ["audit", "--format", "json\u202e", "absent.odt"],
    ],
)
def test_parser_errors_escape_terminal_controls_before_execution(
    arguments: list[str],
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as raised:
        main(arguments)
    assert raised.value.code == 4
    captured = capsys.readouterr()
    assert not captured.out
    assert "\x1b" not in captured.err
    assert "\u202e" not in captured.err
    assert "\nInjected" not in captured.err
    if "--hostile" in arguments[-1]:
        assert r"\x1b" in captured.err
        assert r"\x0a" in captured.err
    assert not list(tmp_path.iterdir())
