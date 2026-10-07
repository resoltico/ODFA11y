# SPDX-License-Identifier: MPL-2.0
"""Validate the TOML configuration: strict keys, exact types, canonical operation order."""

from __future__ import annotations

from pathlib import Path

import pytest

from odfa11y.config import load_config
from odfa11y.errors import ConfigError
from odfa11y.fidelity import FidelityPolicy
from odfa11y.remediation import (
    AltText,
    LinkifyAddresses,
    MarkHeaderRows,
    NormalizeSpacing,
    RemoveEmptySpacers,
    SetAltText,
    SetMetadata,
    SetOdfVersion,
)

FULL = """
[document]
odf_version = "1.3"
title = "Decision"
description = "Decision letter"
language = "en-GB"

[remediation]
linkify_plain_addresses = true
remove_empty_spacers = true

[table_headers]
Data = 1

[alt_text.Logo]
title = "Organisation"
description = "Organisation logo."

[spacing]
reference_text = "Reference"
target_styles = ["BodyTight"]
exact_reference = true

[fidelity]
pagination = "may-change"
raster_tolerance = 0.3
ink_threshold = 180
dpi = 100
"""


def write(tmp_path: Path, text: str) -> Path:
    """Write a configuration file.

    Returns
    -------
    Path
        The file path.

    """
    path = tmp_path / "odfa11y.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_full_configuration_yields_operations_in_canonical_order(tmp_path: Path) -> None:
    config = load_config(write(tmp_path, FULL))
    assert config.operations == (
        SetOdfVersion("1.3"),
        SetMetadata("Decision", "Decision letter", "en-GB"),
        LinkifyAddresses(),
        RemoveEmptySpacers(),
        SetAltText({"Logo": AltText("Organisation", "Organisation logo.")}),
        MarkHeaderRows({"Data": 1}),
        NormalizeSpacing("Reference", ("BodyTight",), exact_reference=True),
    )
    assert config.fidelity == FidelityPolicy("may-change", 0.3, 180, 100)


def test_empty_configuration_requests_nothing(tmp_path: Path) -> None:
    config = load_config(write(tmp_path, ""))
    assert config.operations == ()
    assert config.fidelity == FidelityPolicy()


def test_false_flags_request_nothing(tmp_path: Path) -> None:
    text = "[remediation]\nlinkify_plain_addresses = false\nremove_empty_spacers = false\n"
    assert load_config(write(tmp_path, text)).operations == ()


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ('[document]\ntitel = "Typo"', "Unknown document keys"),
        ("[document]\nlanguage = 7", "document.language must be str"),
        ('[document]\nodf_version = "1.2"', "document.odf_version must be one of"),
        ('[remediation]\nlinkify_plain_addresses = "false"', "must be bool"),
        ("[table_headers]\nData = true", "must be int"),
        ("[table_headers]\nData = 0", "must be a positive integer"),
        ("[alt_text.Logo]\ndescription = 7", "must be str"),
        ('[alt_text.Logo]\ndescripton = "Typo"', "Unknown alt_text.Logo keys"),
        ('document = "invalid"', "must be a table"),
        ("[unknown]", "Unknown configuration keys"),
        ('[spacing]\nreference_text = "x"', "spacing.target_styles must be"),
        ('[spacing]\ntarget_styles = ["A"]', "spacing.reference_text must be"),
        (
            '[spacing]\nreference_text = "x"\ntarget_styles = ["A"]\nexact = true',
            "Unknown spacing keys",
        ),
        ('[fidelity]\npagination = "never"', "fidelity.pagination must be one of"),
        ("[fidelity]\nraster_tolerance = -1", "non-negative number"),
        ("[fidelity]\nink_threshold = 300", "0-255"),
        ("[fidelity]\ndpi = 0", "dpi positive"),
        ("not = valid = toml", "Cannot read configuration"),
    ],
)
def test_invalid_configuration_is_rejected(tmp_path: Path, content: str, message: str) -> None:
    with pytest.raises(ConfigError, match=message):
        load_config(write(tmp_path, content))


def test_missing_configuration_file_is_a_config_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="Cannot read configuration"):
        load_config(tmp_path / "absent.toml")


def test_example_configuration_is_valid(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    guide = (root / "docs/CONFIGURATION.md").read_text(encoding="utf-8")
    assert guide.count("```toml\n") == 1
    example = guide.split("```toml\n", 1)[1].split("\n```", 1)[0]
    config = load_config(write(tmp_path, example))
    assert (
        SetMetadata("Example report", "Summary of the reporting period", "en-GB")
        in config.operations
    )
