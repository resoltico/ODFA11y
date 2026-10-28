# SPDX-License-Identifier: MPL-2.0
"""Family implementations must supply audit and protected-content semantics."""

from __future__ import annotations

lazy from pathlib import Path

import pytest

from odfa11y.adapter import FamilyAdapter, PreservationSnapshot
from odfa11y.families import REGISTRY
from odfa11y.odf import OdfDocument

from .fixtures import make_minimal_odt


def test_incomplete_family_cannot_be_registered_as_an_instance() -> None:
    with pytest.raises(TypeError, match="abstract"):
        FamilyAdapter()  # ty: ignore[call-non-callable]  Negative control: incomplete contracts cannot execute.


def test_family_snapshots_are_immutable_typed_values(tmp_path: Path) -> None:
    document = OdfDocument.open(make_minimal_odt(tmp_path / "source.odt"))
    assert document.kind is not None
    snapshot = REGISTRY[document.kind.family].snapshot(document)
    assert isinstance(snapshot, PreservationSnapshot)
    assert isinstance(snapshot.content, tuple)
    with pytest.raises(AttributeError):
        snapshot.content = ()  # ty: ignore[invalid-assignment]  Frozen protected facts cannot be rewritten by a caller.
