# SPDX-License-Identifier: MPL-2.0
"""Observe native resources using synthetic assets and a healthy loopback server."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import threading
from http import HTTPStatus
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from odfa11y.audit import audit_odf
from odfa11y.evidence import require_free_directory
from odfa11y.fidelity import FidelityPolicy
from odfa11y.odf import NS, OdfDocument, Part, qn
from odfa11y.pdf import EXPORT_OPTIONS, ExportSettings, export_pdfua, find_soffice, identify_soffice
from odfa11y.pipeline import PipelineOptions, run_pipeline
from tests.native_resource_fixtures import (
    PIXELS,
    author_package,
    decoded_images,
    png_bytes,
    writer_resource,
)


def observe(output: Path, soffice: str) -> dict[str, object]:
    """Produce actual PDF observations while independently proving the intended asset control.

    Returns
    -------
    dict[str, object]
        Tool/options/profile identities, healthy responder and per-layout asset/request results.
        External observations are not portable guarantees or a sandbox assertion.

    Raises
    ------
    RuntimeError
        The responder or independent embedded-image control fails.

    """
    require_free_directory(output)
    output.mkdir(parents=True, exist_ok=True)
    requests: list[str] = []
    png = png_bytes()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            requests.append(self.path)
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(png)))
            self.end_headers()
            self.wfile.write(png)

        def log_message(self, *args: object, **kwargs: object) -> None:
            """Keep HTTP diagnostics out of the native tool record."""

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
        try:
            connection.request("GET", "/health")
            response = connection.getresponse()
            healthy = response.status == HTTPStatus.OK and response.read() == png
        finally:
            connection.close()
        if not healthy or requests != ["/health"]:
            msg = "Loopback responder control failed"
            raise RuntimeError(msg)
        requests.clear()
        results = _layouts(output, soffice, server.server_port, requests)
    finally:
        server.shutdown()
        server.server_close()
        worker.join(3)
    result = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "libreoffice": identify_soffice(soffice).as_dict(),
        "export_options": EXPORT_OPTIONS,
        "profile_behavior": "fresh default profile per application export; no link refresh enabled",
        "responder_health": healthy,
        "expected_dimensions": [4, 4],
        "expected_rgb_sha256": hashlib.sha256(PIXELS).hexdigest(),
        "cases": results,
        "scope": "Observed requests/assets on this configuration; no network isolation guarantee",
    }
    (output / "observations.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def _layouts(output: Path, soffice: str, port: int, requests: list[str]) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for layout in ("flat", "native-package"):
        directory = output / layout
        directory.mkdir()
        flat = writer_resource(directory)
        original = (
            flat if layout == "flat" else author_package(flat, soffice, directory / "authored")
        )
        asset = original.parent / "assets" / "nested" / "image.png"
        asset.parent.mkdir(parents=True)
        asset.write_bytes(png_bytes())
        positive = export_pdfua(
            original, directory / "embedded.pdf", ExportSettings("writer_pdf_Export", soffice)
        )
        images = decoded_images(positive)
        if ((4, 4), PIXELS) not in images:
            msg = "Embedded native positive did not retain intended decoded image pixels"
            raise RuntimeError(msg)
        for label, href in (
            ("embedded", None),
            ("local", "assets/nested/image.png"),
            ("loopback", f"http://127.0.0.1:{port}/image.png"),
        ):
            source = _variant(original, directory, label, href)
            requests.clear()
            audit_odf(source)
            parser_requests = list(requests)
            requests.clear()
            pdf = export_pdfua(
                source, directory / f"{label}.pdf", ExportSettings("writer_pdf_Export", soffice)
            )
            actual = decoded_images(pdf)
            item: dict[str, object] = {
                "layout": layout,
                "case": label,
                "source_parser_requests": parser_requests,
                "application_library_requests": list(requests),
                "pdf_produced": pdf.is_file(),
                "images": [
                    {"dimensions": size, "rgb_sha256": hashlib.sha256(data).hexdigest()}
                    for size, data in actual
                ],
                "intended_asset_retained": ((4, 4), PIXELS) in actual,
            }
            requests.clear()
            evidence = directory / f"{label}-pipeline"
            run = run_pipeline(
                source,
                [],
                FidelityPolicy(),
                evidence,
                PipelineOptions(profile="verify", soffice=soffice),
            )
            item["pipeline"] = {
                "exit_status": run.exit_status,
                "failed_stage": run.failed_stage,
                "requests": list(requests),
            }
            results.append(item)
    return results


def _variant(original: Path, directory: Path, label: str, href: str | None) -> Path:
    document = OdfDocument.open(original)
    if href is not None:
        image = document.edit(Part.CONTENT).find(".//draw:image", NS)
        if image is None:
            msg = "Native source has no controlled image"
            raise RuntimeError(msg)
        for child in list(image):
            image.remove(child)
        image.set(qn("xlink", "href"), href)
        image.set(qn("xlink", "type"), "simple")
        image.set(qn("xlink", "show"), "embed")
        image.set(qn("xlink", "actuate"), "onLoad")
    path = directory / (label + original.suffix)
    document.save(path)
    return path


def main() -> int:
    """Run a retained synthetic experiment without interpreting absence of requests as isolation.

    Returns
    -------
    int
        Zero after independently controlled observations have been saved.

    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--soffice", type=Path)
    args = parser.parse_args()
    result = observe(args.output, find_soffice(args.soffice))
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
