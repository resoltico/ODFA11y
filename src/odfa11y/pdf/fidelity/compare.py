# SPDX-License-Identifier: MPL-2.0
"""Compare two PDFs: pages, text, links and rendered pixels."""

from collections import Counter
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass, field
from math import ceil, isfinite
from pathlib import Path
from typing import Annotated, Literal

import pypdfium2
from PIL import Image, ImageChops

from odfa11y.contracts import Description
from odfa11y.errors import ToolFailure
from odfa11y.pdf.fidelity.snapshot import read_snapshot
from odfa11y.report import Report
from odfa11y.report.model import ReportKind
from odfa11y.rules import registry as rules
lazy from odfa11y.pdf.fidelity.snapshot import PdfSnapshot
lazy from odfa11y.plans.fidelity import FidelityPolicy, SamePagination

MAX_RENDER_PIXELS = 20_000_000
EXCERPT_CONTEXT = 40
RASTER_SCALE = 1.0  # fixed 72-dpi canvas units
RATIO_PRECISION = 6


type Rasterizer = Callable[
    [tuple[Path, Path], PdfSnapshot, SamePagination, Report, Path | None], list[float] | None
]


@dataclass(frozen=True, slots=True)
class ArtifactCounts:
    source: int
    candidate: int


@dataclass(frozen=True, slots=True)
class FidelityMeasurements:
    """Measurements produced by pdf-fidelity analysis; None denotes unmeasured data."""

    producer: Literal["pdf-fidelity"] = field(default="pdf-fidelity", init=False)
    policy: Annotated[FidelityPolicy | None, Description("Effective comparison policy.")] = None
    page_count: Annotated[
        ArtifactCounts | None, Description("Source and candidate page counts.")
    ] = None
    link_count: Annotated[
        ArtifactCounts | None, Description("Established external URI destination counts.")
    ] = None
    raster_changed_ratios: Annotated[
        list[float] | None, Description("Changed-pixel ratio for each compared page.")
    ] = None
    raster_max_changed_ratio: Annotated[
        float | None, Description("Largest changed-pixel ratio.")
    ] = None


def compare_pdfs(
    source: str | Path,
    candidate: str | Path,
    policy: FidelityPolicy,
    *,
    diff_dir: str | Path | None = None,
    render: Rasterizer | None = None,
) -> Report:
    """Compare a candidate PDF with its source PDF under a fidelity policy.

    Returns
    -------
    Report
        Findings for every difference the policy forbids; metadata records the measurements.
        When a page differs beyond the tolerance and ``diff_dir`` is given, a PNG marking the
        changed pixels is written there.

    """
    source, candidate = Path(source), Path(candidate)
    report = Report(
        kind=ReportKind.FIDELITY,
        subject=f"{candidate.name} vs {source.name}",
        _sources=(candidate, source),
    )
    report.measure(FidelityMeasurements(policy=policy))
    before, after = read_snapshot(source), read_snapshot(candidate)
    report.measure(
        FidelityMeasurements(page_count=ArtifactCounts(len(before.pages), len(after.pages)))
    )
    for artifact, snapshot in (("source", before), ("candidate", after)):
        for issue in snapshot.issues:
            report.raise_(
                rules.FIDELITY008,
                details={"artifact": artifact, "page": issue.page, "problem": issue.problem},
            )
    _compare_text(before, after, report)
    _compare_links(before, after, report)
    if isinstance(policy, SamePagination) and _compare_pages(before, after, report):
        _compare_raster(
            (source, candidate),
            before,
            policy,
            report,
            Path(diff_dir) if diff_dir else None,
            render=render,
        )
    return report


def _compare_text(before: PdfSnapshot, after: PdfSnapshot, report: Report) -> None:
    if before.text == after.text:
        return
    position = next(
        (i for i, (a, b) in enumerate(zip(before.text, after.text, strict=False)) if a != b),
        min(len(before.text), len(after.text)),
    )
    start = max(position - EXCERPT_CONTEXT, 0)
    report.raise_(
        rules.FIDELITY003,
        details={
            "position": position,
            "source": before.text[start : position + EXCERPT_CONTEXT],
            "candidate": after.text[start : position + EXCERPT_CONTEXT],
        },
    )


def _compare_links(before: PdfSnapshot, after: PdfSnapshot, report: Report) -> None:
    original = Counter(dict(before.links))
    changed = Counter(dict(after.links))
    missing = original - changed
    added = changed - original
    report.measure(
        FidelityMeasurements(
            link_count=ArtifactCounts(sum(original.values()), sum(changed.values()))
        )
    )
    if missing:
        report.raise_(rules.FIDELITY004, details={"missing": sorted(missing.elements())})
    if added:
        report.raise_(rules.FIDELITY006, details={"added": sorted(added.elements())})


def _compare_pages(before: PdfSnapshot, after: PdfSnapshot, report: Report) -> bool:
    if len(before.pages) != len(after.pages):
        report.raise_(
            rules.FIDELITY001, details={"source": len(before.pages), "candidate": len(after.pages)}
        )
        return False
    resized = [
        index + 1
        for index, (a, b) in enumerate(zip(before.pages, after.pages, strict=True))
        if (a.width, a.height) != (b.width, b.height)
    ]
    if resized:
        report.raise_(rules.FIDELITY002, details={"pages": resized})
        return False
    return True


def _compare_raster(
    paths: tuple[Path, Path],
    snapshot: PdfSnapshot,
    policy: SamePagination,
    report: Report,
    diff_dir: Path | None,
    *,
    render: Rasterizer | None,
) -> None:
    try:
        original, changed = (_render_sizes(path, len(snapshot.pages)) for path in paths)
        resized = [
            index + 1 for index, (a, b) in enumerate(zip(original, changed, strict=True)) if a != b
        ]
        if resized:
            report.raise_(rules.FIDELITY002, details={"pages": resized})
            return
        oversized = [
            index + 1
            for index, (width, height) in enumerate(original)
            if width * height > MAX_RENDER_PIXELS
        ]
        if oversized:
            report.raise_(
                rules.FIDELITY007, details={"pages": oversized, "pixel_limit": MAX_RENDER_PIXELS}
            )
            return
        ratios = (render or render_pages)(paths, snapshot, policy, report, diff_dir)
    except pypdfium2.PdfiumError as error:
        message = f"Cannot render PDF for comparison: {error}"
        raise ToolFailure(message) from error
    if ratios is not None:
        report.measure(FidelityMeasurements(raster_changed_ratios=ratios))
        report.measure(FidelityMeasurements(raster_max_changed_ratio=max(ratios, default=0.0)))


def _render_sizes(path: Path, expected_pages: int) -> tuple[tuple[int, int], ...]:
    sizes = []
    with closing(pypdfium2.PdfDocument(path)) as document:
        if len(document) != expected_pages:
            message = "PDF page count changed during comparison"
            raise ToolFailure(message)
        for index in range(len(document)):
            with closing(document[index]) as page:
                sizes.append(_bitmap_size(page))
    return tuple(sizes)


def _bitmap_size(page: pypdfium2.PdfPage) -> tuple[int, int]:
    width, height = page.get_size()
    if not all(isfinite(value) and value > 0 for value in (width, height)):
        message = "PDF page has an unrenderable geometry"
        raise ToolFailure(message)
    return ceil(width * RASTER_SCALE), ceil(height * RASTER_SCALE)


def _difference(
    left: Image.Image, right: Image.Image, ink_threshold: int
) -> tuple[float, Image.Image]:
    if left.size != right.size:
        message = "Raster geometry must match before comparing pixels"
        raise ValueError(message)
    lookup = [255 if value < ink_threshold else 0 for value in range(256)]
    ink_left = left.convert("L").point(lookup).convert("1")
    ink_right = right.convert("L").point(lookup).convert("1")
    moved = ImageChops.logical_xor(ink_left, ink_right)
    ink = max(ink_left.histogram()[255], ink_right.histogram()[255], 1)
    return moved.histogram()[255] / ink, moved.convert("L")


def render_pages(
    paths: tuple[Path, Path],
    snapshot: PdfSnapshot,
    policy: SamePagination,
    report: Report,
    diff_dir: Path | None,
) -> list[float] | None:
    ratios = []
    with (
        closing(pypdfium2.PdfDocument(paths[0])) as reference,
        closing(pypdfium2.PdfDocument(paths[1])) as changed,
    ):
        if len(reference) != len(snapshot.pages) or len(changed) != len(snapshot.pages):
            message = "PDF page count changed during comparison"
            raise ToolFailure(message)
        for index in range(len(snapshot.pages)):
            with closing(reference[index]) as left_page, closing(changed[index]) as right_page:
                left_size, right_size = _bitmap_size(left_page), _bitmap_size(right_page)
                if left_size != right_size:
                    report.raise_(rules.FIDELITY002, details={"pages": [index + 1]})
                    return None
                if left_size[0] * left_size[1] > MAX_RENDER_PIXELS:
                    report.raise_(
                        rules.FIDELITY007,
                        details={"pages": [index + 1], "pixel_limit": MAX_RENDER_PIXELS},
                    )
                    return None
                left, right = _render_pair(left_page, right_page)
            if left.size != right.size:
                report.raise_(rules.FIDELITY002, details={"pages": [index + 1]})
                return None
            ratio, mask = _difference(left, right, policy.ink_threshold)
            ratios.append(round(ratio, RATIO_PRECISION))
            if ratio > policy.raster_tolerance:
                _raster_finding(report, diff_dir, index + 1, ratios[-1], mask)
    return ratios


def _render_pair(
    left: pypdfium2.PdfPage, right: pypdfium2.PdfPage
) -> tuple[Image.Image, Image.Image]:
    with closing(left.render(scale=RASTER_SCALE)) as bitmap:
        original = bitmap.to_pil().convert("RGB")
    with closing(right.render(scale=RASTER_SCALE)) as bitmap:
        changed = bitmap.to_pil().convert("RGB")
    return original, changed


def _raster_finding(
    report: Report, diff_dir: Path | None, page: int, ratio: float, mask: Image.Image
) -> None:
    details: dict[str, object] = {"page": page, "changed_ratio": ratio}
    if diff_dir is not None:
        diff_dir.mkdir(parents=True, exist_ok=True)
        path = diff_dir / f"page-{page:03d}-diff.png"
        mask.save(path)
        details["diff_image"] = path.name
    report.raise_(rules.FIDELITY005, details=details)
