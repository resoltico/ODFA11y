# SPDX-License-Identifier: MPL-2.0
"""Negative controls prove that silent payload/data damage cannot be published."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, cast, override

import pytest

from odfa11y.adapter import Operation, Outcome, Status
from odfa11y.content import GraphicDescription
from odfa11y.errors import RemediationError
from odfa11y.families.text import SetGraphicDescriptions
from odfa11y.odf import OdfDocument, PackageStorage, Part, qn, select_elements
from odfa11y.remediation import remediate

from .documents import Variant, make_flat
from .fixtures import make_minimal_odt

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True, slots=True)
class DamagePayload(Operation):
    """Deliberately damage a resource without touching visible words."""

    member: str | None = None
    name: ClassVar[str] = "damage_payload"

    @override
    def apply(self, document: OdfDocument) -> tuple[Outcome, ...]:
        tree = document.edit(Part.CONTENT)
        if self.member is None:
            select_elements(tree, "//office:binary-data")[0].text = "YmFk"
        else:
            assert isinstance(document.storage, PackageStorage)
            document.storage.write_member(self.member, b"damaged")
        return (Outcome(self.name, Status.APPLIED, "Damaged payload", count=1),)


@dataclass(frozen=True, slots=True)
class DamageCellValue(Operation):
    """Deliberately change a numeric value while retaining its displayed words."""

    name: ClassVar[str] = "damage_cell_value"

    @override
    def apply(self, document: OdfDocument) -> tuple[Outcome, ...]:
        cell = select_elements(document.edit(Part.CONTENT), "//table:table-cell")[0]
        cell.set(qn("office", "value"), "99")
        return (Outcome(self.name, Status.APPLIED, "Damaged value", count=1),)


@pytest.mark.parametrize("member", ["Pictures/logo.svg", "metadata.rdf", "database/firebird.fbk"])
def test_opaque_package_resource_damage_is_rejected(tmp_path: Path, member: str) -> None:
    source = make_minimal_odt(tmp_path / "source.odt", with_image_without_alt=True)
    storage = PackageStorage(source)
    storage.write_member(member, b"original")
    storage.save(source)
    original = source.read_bytes()
    destination = tmp_path / "out.odt"
    with pytest.raises(RemediationError, match="Opaque document resources changed"):
        remediate(source, destination, [DamagePayload(member)])
    assert source.read_bytes() == original
    assert not destination.exists()


def test_flat_embedded_binary_damage_is_rejected(tmp_path: Path) -> None:
    body = (
        '<office:text><text:p><draw:frame draw:name="Picture">'
        "<draw:image><office:binary-data>b3JpZ2luYWw=</office:binary-data></draw:image>"
        "</draw:frame></text:p></office:text>"
    )
    source = make_flat(tmp_path, "text", Variant(body=body))
    destination = tmp_path / "out.fodt"
    with pytest.raises(RemediationError, match="Opaque document resources changed"):
        remediate(source, destination, [DamagePayload()])
    assert not destination.exists()


def test_protected_cell_value_change_is_rejected_even_without_changed_words(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "source.odt", with_data_table=True)
    destination = tmp_path / "out.odt"
    with pytest.raises(RemediationError, match="content changed"):
        remediate(source, destination, [DamageCellValue()])
    assert not destination.exists()


def test_direct_graphic_api_rejects_nonstring_metadata_before_any_edit(tmp_path: Path) -> None:
    source = make_minimal_odt(tmp_path / "source.odt", with_image_without_alt=True)

    doc = OdfDocument.open(source)
    operation = SetGraphicDescriptions({"Logo": GraphicDescription(description=cast("str", 7))})
    assert operation.apply(doc)[0].status is Status.FAILED
    assert doc.edit_count == 0
