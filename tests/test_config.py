# SPDX-License-Identifier: MPL-2.0
"""Validate TOML remediation configuration and reject malformed input."""

from __future__ import annotations

from pathlib import Path

import pytest

from odfa11y.remediation import load_remediation_config


def test_toml_configuration_loads_explicit_semantics(tmp_path: Path) -> None:
    path = tmp_path / "odfa11y.toml"
    path.write_text(
        """
[document]
target_version = "1.4"
title = "Decision"
description = "Decision letter"
language = "en-GB"

[remediation]
linkify_plain_addresses = true
remove_empty_spacers = false

[table_headers]
Data = 1

[alt_text.Logo]
title = "Organisation"
description = "Organisation logo."
""",
        encoding="utf-8",
    )
    options = load_remediation_config(path)
    assert options.target_version == "1.4"
    assert options.title == "Decision"
    assert options.description == "Decision letter"
    assert options.language == "en-GB"
    assert options.linkify_plain_addresses is True
    assert options.table_header_rows == {"Data": 1}
    assert options.alt_text is not None
    assert options.alt_text["Logo"].description == "Organisation logo."


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ('[document]\ntitel = "Typo"', "Unknown document keys"),
        ("[document]\nlanguage = 7", "document.language must be str"),
        ('[remediation]\nlinkify_plain_addresses = "false"', "must be bool"),
        ("[table_headers]\nData = true", "must be int"),
        ("[table_headers]\nData = 0", "must be a positive integer"),
        ("[alt_text.Logo]\ndescription = 7", "must be str"),
        ('[alt_text.Logo]\ndescripton = "Typo"', "Unknown alt_text.Logo keys"),
        ('document = "invalid"', "must be a table"),
        ("[unknown]", "Unknown configuration keys"),
    ],
)
def test_invalid_configuration_is_rejected(tmp_path: Path, content: str, message: str) -> None:
    path = tmp_path / "invalid.toml"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        load_remediation_config(path)


def test_empty_configuration_retains_safe_defaults(tmp_path: Path) -> None:
    path = tmp_path / "empty.toml"
    path.write_text("", encoding="utf-8")
    options = load_remediation_config(path)
    assert options.target_version == "1.4"
    assert options.linkify_plain_addresses is False
    assert options.table_header_rows is None


def test_example_configuration_is_valid(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    guide = (root / "docs/CONFIGURATION.md").read_text(encoding="utf-8")
    assert guide.count("```toml\n") == 1
    example = guide.split("```toml\n", 1)[1].split("\n```", 1)[0]
    config = tmp_path / "document.toml"
    config.write_text(example, encoding="utf-8")
    assert load_remediation_config(config).language == "en-GB"
