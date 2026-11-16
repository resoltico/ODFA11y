# SPDX-License-Identifier: MPL-2.0
"""Family implementations must supply audit and protected-content semantics."""

lazy from pathlib import Path

import pytest

from odfa11y.families import REGISTRY
from odfa11y.families.spec import FamilySpec
from odfa11y.odf import Family, OdfDocument
from tests.fixtures.writer import make_minimal_odt


def test_incomplete_family_cannot_be_registered_as_an_instance() -> None:
    with pytest.raises(TypeError, match="required positional"):
        FamilySpec()  # ty: ignore[missing-argument]  Negative control: incomplete contracts cannot execute.


def test_family_capabilities_are_immutable_typed_values(tmp_path: Path) -> None:
    document = OdfDocument.open(make_minimal_odt(tmp_path / "source.odt"))
    assert document.kind is not None
    spec = REGISTRY[document.kind.family]
    assert spec.family is Family.TEXT
    assert isinstance(spec.kinds, tuple)
    with pytest.raises(AttributeError):
        spec.family = Family.CHART  # ty: ignore[invalid-assignment]  Frozen capabilities cannot be rewritten by a caller.
