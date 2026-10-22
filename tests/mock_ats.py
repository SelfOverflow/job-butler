"""Local mock ATS for browser tests: serves fixture forms and records submissions."""

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

FORMS = Path(__file__).resolve().parent / "fixtures" / "forms"


@dataclass
class MockATS:
    base_url: str
    submissions: list[bytes] = field(default_factory=list)

    def url(self, page: str) -> str:
        return f"{self.base_url}/{page}"


@contextmanager
def mock_ats() -> Iterator[MockATS]:
    state = MockATS(base_url="")

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(*args, directory=str(FORMS), **kwargs)  # type: ignore[arg-type]

        def do_POST(self) -> None:  # noqa: N802 - http.server naming
            length = int(self.headers.get("Content-Length", 0))
            state.submissions.append(self.rfile.read(length))
            body = b"<html><body><h1>Thank you for applying!</h1></body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args: object) -> None:
            pass  # Keep test output quiet.

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    state.base_url = f"http://127.0.0.1:{server.server_address[1]}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()
