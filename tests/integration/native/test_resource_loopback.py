# SPDX-License-Identifier: MPL-2.0
"""A functioning responder independently pairs guarded refusals with request observations."""

import threading
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
lazy from collections.abc import Callable
lazy from pathlib import Path

from odfa11y.application.tools import Tools
from odfa11y.cli import main
from odfa11y.evidence import check_bundle
from odfa11y.plans.fidelity import Pagination
from odfa11y.run.context import RunSettings
from odfa11y.run.engine import execute
from odfa11y.run.profiles import profile_named
from tests.fixtures.declarations import declaration
from tests.fixtures.native_resources import png_bytes
from tests.fixtures.plans import reviewed_plan


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
            record = execute(
                source,
                reviewed_plan(source, [], Pagination.SAME()),
                output,
                RunSettings(tools=Tools(soffice=soffice), profile=profile_named("verify")),
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
