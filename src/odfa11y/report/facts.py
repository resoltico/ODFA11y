# SPDX-License-Identifier: MPL-2.0
"""Registered measurements and their declared value types."""

from __future__ import annotations

import types
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast, get_args, get_origin

from odfa11y.errors import ReportError

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping


@dataclass(frozen=True, slots=True)
class FactKey[T]:
    """A stable measurement identity, value type and human-readable description."""

    id: str
    value_type: object
    description: str


FACT_REGISTRY: dict[str, FactKey[object]] = {}


def _register[T](key: FactKey[T]) -> FactKey[T]:
    if key.id in FACT_REGISTRY:
        msg = f"Fact {key.id!r} is already registered."
        raise ReportError(msg)
    FACT_REGISTRY[key.id] = cast("FactKey[object]", key)
    return key


class FactKeys:
    """The source of report measurement identities and their schemas."""

    DOCUMENT_ADAPTER = _register(
        FactKey[str]("document.adapter", str, "Family adapter used for source semantics.")
    )
    PACKAGE_LAYOUT = _register(FactKey[str]("package.layout", str, "Physical ODF representation."))
    DOCUMENT_MEDIA_TYPE = _register(
        FactKey[str | None]("document.media_type", str | None, "Declared source media type.")
    )
    DOCUMENT_KIND = _register(FactKey[str]("document.kind", str, "Detected ODF document kind."))
    DOCUMENT_FAMILY = _register(FactKey[str]("document.family", str, "Detected ODF family."))
    DOCUMENT_ODF_VERSION = _register(
        FactKey[str]("document.odf_version", str, "Declared ODF version.")
    )
    SCHEMA_VERSION = _register(
        FactKey[str | None]("schema.version", str | None, "Version of the selected bundled schema.")
    )
    SCHEMA_VIOLATION_COUNT = _register(
        FactKey[int]("schema.violation_count", int, "Reported schema violations.")
    )
    SCHEMA_UNLOCATED_VIOLATION_COUNT = _register(
        FactKey[int](
            "schema.unlocated_violation_count",
            int,
            "Violations without established element locations.",
        )
    )
    NATIVE_LIMITATIONS = _register(
        FactKey[dict[str, int]](
            "native.limitations",
            dict[str, int],
            "Counts of declarations requiring native export refusal or review.",
        )
    )
    TEXT_PARAGRAPH_STYLES = _register(
        FactKey[list[dict[str, object]]](
            "text.paragraph_styles",
            list[dict[str, object]],
            "Paragraph style usage and effective spacing.",
        )
    )
    TEXT_LIST_COUNT = _register(
        FactKey[int]("text.list_count", int, "Lists in established current reading contexts.")
    )
    TEXT_LIST_MAX_LEVEL = _register(
        FactKey[int](
            "text.list_max_level", int, "Deepest counter level, resetting at cells and text boxes."
        )
    )
    TEXT_LIST_CONTINUATION_COUNT = _register(
        FactKey[int](
            "text.list_continuation_count", int, "Resolved list continuation relationships."
        )
    )
    TEXT_SIMULATED_LIST_COUNT = _register(
        FactKey[int](
            "text.simulated_list_count",
            int,
            "Paragraphs resembling typed list markers; review only.",
        )
    )
    TEXT_HEADING_COUNT = _register(
        FactKey[int]("text.heading_count", int, "Structural headings in current reading contexts.")
    )
    TEXT_GRAPHIC_COUNT = _register(
        FactKey[int]("text.graphic_count", int, "Graphic objects in current reading contexts.")
    )
    TEXT_TABLE_COUNT = _register(
        FactKey[int]("text.table_count", int, "Tables in current reading contexts.")
    )
    SHEET_COUNT = _register(FactKey[int]("sheet.count", int, "Sheets in document order."))
    PAGE_COUNT = _register(FactKey[int]("page.count", int, "Drawing or presentation pages."))
    PAGE_SHAPE_COUNT = _register(
        FactKey[int]("page.shape_count", int, "Shapes on drawing or presentation pages.")
    )
    PAGE_LINK_COUNT = _register(
        FactKey[int]("page.link_count", int, "Links on drawing or presentation pages.")
    )
    FORMULA_ELEMENT_COUNT = _register(
        FactKey[int]("formula.element_count", int, "Inspected MathML elements.")
    )
    DATABASE_CONNECTION_DECLARATION_COUNT = _register(
        FactKey[int](
            "database.connection_declaration_count", int, "Database connection declarations."
        )
    )
    DATABASE_QUERY_DECLARATION_COUNT = _register(
        FactKey[int]("database.query_declaration_count", int, "Declared database queries.")
    )
    IMAGE_GRAPHIC_COUNT = _register(
        FactKey[int]("image.graphic_count", int, "Graphic frames in an Image document.")
    )
    CHART_COUNT = _register(FactKey[int]("chart.count", int, "Native charts in a Chart document."))
    CHART_SERIES_COUNT = _register(
        FactKey[int]("chart.series_count", int, "Declared chart series.")
    )
    PDF_PAGE_COUNT = _register(FactKey[int]("pdf.page_count", int, "Pages in the inspected PDF."))
    PDF_FORMAT = _register(FactKey[str]("pdf.format", str, "PDF header format declaration."))
    PDF_UA_PART = _register(FactKey[int]("pdf.ua_part", int, "Declared PDF/UA part."))
    PDF_TEXT_CHARACTER_COUNT = _register(
        FactKey[int]("pdf.text_character_count", int, "Extractable text characters.")
    )
    PDF_DESCRIBED_GRAPHIC_COUNT = _register(
        FactKey[int](
            "pdf.described_graphic_count", int, "Inspected graphical content with descriptions."
        )
    )
    PDF_MARKED_CONTENT_ID_COUNT = _register(
        FactKey[int]("pdf.marked_content_id_count", int, "Marked content identifiers.")
    )
    PDF_LINK_ANNOTATION_COUNT = _register(
        FactKey[int]("pdf.link_annotation_count", int, "Inspected link annotations.")
    )
    PDF_LINK_STRUCTURE_ELEMENT_COUNT = _register(
        FactKey[int](
            "pdf.link_structure_element_count", int, "Link elements in the structure tree."
        )
    )
    PDF_STRUCTURE_TAGS = _register(
        FactKey[dict[str, int]](
            "pdf.structure_tags", dict[str, int], "Reachable structure roles and their counts."
        )
    )
    PDF_ROLE_MAP = _register(
        FactKey[dict[str, str]](
            "pdf.role_map", dict[str, str], "PDF custom-to-standard structure role mapping."
        )
    )
    VERAPDF_IDENTITY = _register(
        FactKey[dict[str, str | int | bool]](
            "verapdf.identity",
            dict[str, str | int | bool],
            "Validator identity, profile, verdict and failed-rule count.",
        )
    )
    FIDELITY_POLICY = _register(
        FactKey[dict[str, str | int | float | bool]](
            "fidelity.policy", dict[str, str | int | float | bool], "Effective comparison policy."
        )
    )
    FIDELITY_LINK_COUNT = _register(
        FactKey[dict[str, int]](
            "fidelity.link_count", dict[str, int], "Source and candidate link counts."
        )
    )
    FIDELITY_RASTER_CHANGED_RATIOS = _register(
        FactKey[list[float]](
            "fidelity.raster_changed_ratios",
            list[float],
            "Changed-pixel ratio for each compared page.",
        )
    )
    FIDELITY_RASTER_MAX_CHANGED_RATIO = _register(
        FactKey[float]("fidelity.raster_max_changed_ratio", float, "Largest changed-pixel ratio.")
    )
    DOCUMENT_TITLE = _register(FactKey[str]("document.title", str, "Authored document title."))
    DOCUMENT_DESCRIPTION = _register(
        FactKey[str]("document.description", str, "Authored document description.")
    )
    DOCUMENT_LANGUAGE = _register(
        FactKey[str | None]("document.language", str | None, "Effective document language.")
    )
    SHEET_GRAPHIC_COUNT = _register(
        FactKey[int]("sheet.graphic_count", int, "Graphic objects on sheets.")
    )
    PDF_TITLE = _register(FactKey[str]("pdf.title", str, "PDF document title."))
    PDF_LANGUAGE = _register(FactKey[str]("pdf.language", str, "PDF catalog language."))
    FIDELITY_PAGE_COUNT = _register(
        FactKey[dict[str, int]](
            "fidelity.page_count", dict[str, int], "Source and candidate page counts."
        )
    )


def _matches(value: object, expected: object) -> bool:
    origin = get_origin(expected)
    arguments = get_args(expected)
    if origin is types.UnionType:
        return any(_matches(value, item) for item in arguments)
    if expected is object:
        return True
    if origin is list:
        return isinstance(value, list) and all(_matches(item, arguments[0]) for item in value)
    if origin is dict:
        return isinstance(value, dict) and all(
            _matches(key, arguments[0]) and _matches(item, arguments[1])
            for key, item in value.items()
        )
    if expected is float:
        return type(value) in {int, float}
    if expected in {int, bool}:
        return type(value) is expected
    return isinstance(expected, type) and isinstance(value, expected)


def _require_registered(key: FactKey[object]) -> None:
    if not isinstance(key, FactKey) or FACT_REGISTRY.get(key.id) is not key:
        msg = "Report facts require a registered FactKey."
        raise ReportError(msg)


class FactSet:
    """Store only registered measurements whose values match their declarations."""

    def __init__(self, values: Mapping[FactKey[object], object] | None = None) -> None:
        self._values: dict[str, object] = {}
        for key, value in (values or {}).items():
            self[key] = value

    def __setitem__[T](self, key: FactKey[T], value: T) -> None:
        """Record a value that satisfies its registered declaration.

        Raises
        ------
        ReportError
            The key is unregistered or the value violates its declared type.

        """
        _require_registered(key)
        if not _matches(value, key.value_type):
            msg = f"Fact {key.id!r} requires {key.value_type}, found {type(value).__name__}."
            raise ReportError(msg)
        self._values[key.id] = value

    def __getitem__[T](self, key: FactKey[T]) -> T:
        """Return the recorded measurement for a typed key.

        Returns
        -------
        T
            The recorded measurement.

        """
        _require_registered(key)
        return cast("T", self._values[key.id])

    def get[T](self, key: FactKey[T], default: T | None = None) -> T | None:
        """Read a registered measurement, returning the default when absent.

        Returns
        -------
        T | None
            The recorded value, or the requested default.

        """
        _require_registered(key)
        return cast("T | None", self._values.get(key.id, default))

    def __iter__(self) -> Iterator[FactKey[object]]:
        """Iterate over registered keys present in this set.

        Returns
        -------
        Iterator[FactKey[object]]
            The recorded identities.

        """
        return (FACT_REGISTRY[key] for key in self._values)

    def __len__(self) -> int:
        """Count the recorded measurements.

        Returns
        -------
        int
            The number of recorded keys.

        """
        return len(self._values)

    def keys(self) -> set[FactKey[object]]:
        """Return the recorded keys.

        Returns
        -------
        set[FactKey[object]]
            Registered identities present in this report.

        """
        return set(self)

    def as_dict(self) -> dict[str, object]:
        """Serialize the measured values using stable namespaced identifiers.

        Returns
        -------
        dict[str, object]
            Recorded facts, without Python registry objects.

        """
        return dict(self._values)
