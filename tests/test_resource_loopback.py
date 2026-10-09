# SPDX-License-Identifier: MPL-2.0
"""A functioning responder independently pairs guarded refusals with request observations."""

from __future__ import annotations

import threading
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING

import pytest

from odfa11y.cli import main
from odfa11y.evidence import check_bundle
from odfa11y.fidelity import FidelityPolicy
from odfa11y.pipeline import PipelineOptions, run_pipeline

from .native_resource_fixtures import png_bytes
from .resource_declaration_fixtures import declaration

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

pytestmark = pytest.mark.integration


def test_healthy_loopback_declarations_refuse_before_real_native_boundary(
    tmp_path: Path, external_tool: Callable[..., str]
) -> None:
    soffice = external_tool("soffice", "libreoffice")
    requests = []
    payload = png_bytes()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            requests.append(self.path)
            self.send_response(200)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args: object, **kwargs: object) -> None:
            """Keep responder diagnostics out of native test output."""

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
        connection.request("GET", "/health")
        response = connection.getresponse()
        assert response.status == 200
        assert response.read() == payload
        connection.close()
        assert requests == ["/health"]
        requests.clear()
        for kind in ["fill", "bullet", "symbol", "font", "form-image"]:
            source = declaration(tmp_path, kind, f"http://127.0.0.1:{server.server_port}/asset.png")
            assert (
                main(["export", str(source), str(tmp_path / "native.pdf"), "--soffice", soffice])
                == 3
            )
            output = tmp_path / kind
            record = run_pipeline(
                source,
                [],
                FidelityPolicy(),
                output,
                PipelineOptions(profile="verify", soffice=soffice),
            )
            assert record.failed_stage == "export-source"
            assert record.exit_status == 3
            assert check_bundle(output) == []
        assert requests == []  # Preflight refusal, not OS network isolation.
    finally:
        server.shutdown()
        server.server_close()
        worker.join(3)
    assert not worker.is_alive()
