# SPDX-License-Identifier: MPL-2.0
"""Check exact changelog-section extraction and meaningful rejection cases."""

from __future__ import annotations

import pytest

from tools.check_release import extract_release_notes


def test_matching_section_preserves_heading_wording_and_markdown() -> None:
    section = (
        "## [1.2.3] - 2026-01-01\n\n### Changed\n\n"
        "- Exact **wording**, with [a link](https://example.invalid).\n"
        "  Continuation retains its indentation."
    )
    changelog = (
        "# Changelog\n\n## [Unreleased]\n\nPending work.\n\n"
        + section
        + "\n\n## [1.2.2] - 2025-12-01\n\nOlder news.\n"
    )
    assert extract_release_notes(changelog, "1.2.3") == section


@pytest.mark.parametrize(
    "heading", ["## [1.2.30]", "## [1.2.3]x", "## [1]x2y3", "### [1.2.3]", "##1.2.3"]
)
def test_version_heading_is_matched_literally(heading: str) -> None:
    with pytest.raises(ValueError, match="no section"):
        extract_release_notes(heading + "\n\nOther notes.\n", "1.2.3")


def test_first_line_and_last_section_are_supported() -> None:
    section = "## [1.2.3]\n\nFirst release."
    assert extract_release_notes(section + "\n", "1.2.3") == section


def test_empty_section_does_not_include_the_following_release() -> None:
    assert extract_release_notes("## [1.2.3]\n## [1.2.2]\nOld news.\n", "1.2.3") == "## [1.2.3]"


def test_duplicate_version_sections_are_rejected() -> None:
    with pytest.raises(ValueError, match="multiple sections"):
        extract_release_notes("## [1.2.3]\nA.\n## [1.2.3]\nB.\n", "1.2.3")


def test_internal_line_endings_are_retained() -> None:
    section = "## [1.2.3]\r\n\r\n- Exact notes."
    assert extract_release_notes(section + "\r\n", "1.2.3") == section
