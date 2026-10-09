# SPDX-License-Identifier: MPL-2.0
"""Compare two PDFs: pages, text, links and rendered pixels."""

from __future__ import annotations

import sys
from contextlib import closing
from pathlib import Path
from typing import TYPE_CHECKING

import pypdfium2
from PIL import Image, ImageChops

from odfa11y.errors import ToolFailedError
from odfa11y.report import Report, rules

from .snapshot import read_snapshot

if TYPE_CHECKING:
    from .policy import FidelityPolicy
    from .snapshot import PdfSnapshot

MAX_RENDER_PIXELS = 20_000_000
EXCERPT_CONTEXT = 40
POINTS_PER_INCH = 72
RATIO_PRECISION = 6


def compare_pdfs(
    source: str | Path,
    candidate: str | Path,
    policy: FidelityPolicy,
    *,
    diff_dir: str | Path | None = None,
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
        kind="fidelity", subject=f"{candidate.name} vs {source.name}", sources=(candidate, source)
    )
    report.metadata["policy"] = policy.as_dict()
    before, after = read_snapshot(source), read_snapshot(candidate)
    report.metadata["pages"] = {"source": len(before.pages), "candidate": len(after.pages)}
    _compare_text(before, after, report)
    _compare_links(before, after, report)
    if policy.pagination == "same" and _compare_pages(before, after, report):
        _compare_raster(
            (source, candidate), before, policy, report, Path(diff_dir) if diff_dir else None
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
    report.add(
        rules.FID003,
        details={
            "position": position,
            "source": before.text[start : position + EXCERPT_CONTEXT],
            "candidate": after.text[start : position + EXCERPT_CONTEXT],
        },
    )


def _compare_links(before: PdfSnapshot, after: PdfSnapshot, report: Report) -> None:
    missing = before.links - after.links
    added = after.links - before.links
    report.metadata["links"] = {
        "source": sum(before.links.values()),
        "candidate": sum(after.links.values()),
    }
    if missing:
        report.add(rules.FID004, details={"missing": sorted(missing.elements())})
    if added:
        report.add(rules.FID006, details={"added": sorted(added.elements())})


def _compare_pages(before: PdfSnapshot, after: PdfSnapshot, report: Report) -> bool:
    if len(before.pages) != len(after.pages):
        report.add(
            rules.FID001, details={"source": len(before.pages), "candidate": len(after.pages)}
        )
        return False
    resized = [
        index + 1
        for index, (a, b) in enumerate(zip(before.pages, after.pages, strict=True))
        if (a.width, a.height) != (b.width, b.height)
    ]
    if resized:
        report.add(rules.FID002, details={"pages": resized})
        return False
    return True


def _compare_raster(
    paths: tuple[Path, Path],
    snapshot: PdfSnapshot,
    policy: FidelityPolicy,
    report: Report,
    diff_dir: Path | None,
) -> None:
    if policy.dpi > sys.float_info.max:
        msg = "DPI exceeds the numeric range supported by PDF rendering"
        raise ToolFailedError(msg)
    scale = policy.dpi / POINTS_PER_INCH
    oversized = [
        index + 1
        for index, page in enumerate(snapshot.pages)
        if page.width * page.height * scale * scale > MAX_RENDER_PIXELS
    ]
    if oversized:
        report.add(rules.FID007, details={"pages": oversized, "pixel_limit": MAX_RENDER_PIXELS})
        return
    try:
        ratios = _render_ratios(paths, snapshot, policy, report, diff_dir)
    except pypdfium2.PdfiumError as exc:
        msg = f"Cannot render PDF for comparison: {exc}"
        raise ToolFailedError(msg) from exc
    report.metadata["raster_changed_ratios"] = ratios
    report.metadata["raster_max_changed_ratio"] = max(ratios, default=0.0)


def _difference(
    left: Image.Image, right: Image.Image, ink_threshold: int
) -> tuple[float, Image.Image]:
    if left.size != right.size:
        return 1.0, Image.new("L", left.size, 255)
    lookup = [255 if value < ink_threshold else 0 for value in range(256)]
    ink_left = left.convert("L").point(lookup).convert("1")
    ink_right = right.convert("L").point(lookup).convert("1")
    moved = ImageChops.logical_xor(ink_left, ink_right)
    ink = max(ink_left.histogram()[255], ink_right.histogram()[255], 1)
    return moved.histogram()[255] / ink, moved.convert("L")


def _render_ratios(
    paths: tuple[Path, Path],
    snapshot: PdfSnapshot,
    policy: FidelityPolicy,
    report: Report,
    diff_dir: Path | None,
) -> list[float]:
    scale = policy.dpi / POINTS_PER_INCH
    ratios: list[float] = []
    with (
        closing(pypdfium2.PdfDocument(paths[0])) as reference,
        closing(pypdfium2.PdfDocument(paths[1])) as changed,
    ):
        for index in range(len(snapshot.pages)):
            left = reference[index].render(scale=scale).to_pil().convert("RGB")
            right = changed[index].render(scale=scale).to_pil().convert("RGB")
            ratio, mask = _difference(left, right, policy.ink_threshold)
            ratios.append(round(ratio, RATIO_PRECISION))
            if ratio > policy.raster_tolerance:
                details: dict[str, object] = {"page": index + 1, "changed_ratio": ratios[-1]}
                if diff_dir is not None:
                    diff_dir.mkdir(parents=True, exist_ok=True)
                    path = diff_dir / f"page-{index + 1:03d}-diff.png"
                    mask.save(path)
                    details["diff_image"] = path.name
                report.add(rules.FID005, details=details)
    return ratios
