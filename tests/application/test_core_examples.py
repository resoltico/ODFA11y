# SPDX-License-Identifier: MPL-2.0
"""Execute public library examples against real source fixtures and native boundaries."""

import sys
lazy from collections.abc import Callable
lazy from pathlib import Path

import pytest

from odfa11y import audit
from odfa11y.application.tools import Tools
from odfa11y.errors import ToolFailure
from odfa11y.native.process import run_bounded
from odfa11y.odf import OdfDocument, Part, qn
from odfa11y.records import DoctorRecord, Toolchain
from odfa11y.report import FactKeys
from tests.fixtures.documents import make_flat, make_package
from tools import core_examples


@pytest.mark.parametrize("author", [make_flat, make_package], ids=["flat", "package"])
def test_source_examples_make_only_the_explicit_title_edit_without_terminal_output(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    author: Callable[..., Path],
) -> None:
    source = author(tmp_path, "text")
    before = source.read_bytes()
    work = tmp_path / "work"
    reports = core_examples.inspect_source(source, work)
    assert len(reports) == 2
    assert all(report.kind == "odf" for report in reports)
    reviewed = work / ("reviewed" + source.suffix)
    document = OdfDocument.open(reviewed)
    title = document.tree(Part.META).find(".//" + qn("dc", "title"))
    assert title is not None
    assert title.text == "Reviewed example"
    assert (work / "decisions.toml").is_file()
    assert source.read_bytes() == before
    captured = capsys.readouterr()
    assert not captured.out
    assert not captured.err


def test_example_import_and_execution_never_load_the_cli_in_a_fresh_process(tmp_path: Path) -> None:
    script = """
import sys
from pathlib import Path
from tools.core_examples import inspect_source
from tests.fixtures.documents import make_package
root = Path(sys.argv[1])
source = make_package(root, "text")
inspect_source(source, root / "work")
assert not any(n == "odfa11y.cli" or n.startswith("odfa11y.cli.") for n in sys.modules)
"""
    completed = run_bounded([sys.executable, "-c", script, str(tmp_path)], timeout=30)
    assert completed.returncode == 0, completed.stderr
    assert not completed.stdout
    assert not completed.stderr


def test_style_example_contract_refuses_unsupported_families(tmp_path: Path) -> None:
    source = make_flat(tmp_path, "spreadsheet")
    assert FactKeys.TEXT_PARAGRAPH_STYLES not in audit(source).reports[0].facts


def test_native_example_retains_controlled_probe_failure_before_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = make_flat(tmp_path, "text")
    failure = ToolFailure("Controlled capability probe failure")
    record = DoctorRecord("test", "3.15.2", "test", {}, (), Toolchain(), error=failure)
    monkeypatch.setattr(core_examples.api, "doctor", lambda **_kwargs: record)
    exports = []
    monkeypatch.setattr(core_examples.api, "export", lambda *args, **_kwargs: exports.append(args))
    with pytest.raises(ToolFailure, match="Controlled capability probe failure") as caught:
        core_examples.native_work(source, tmp_path / "work", Tools())
    assert caught.value is failure
    assert exports == []
    assert not (tmp_path / "work" / "publication.pdf").exists()
