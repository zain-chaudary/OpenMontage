#!/usr/bin/env python3
"""Range-capable static server for the agents-make-video deliverable.

Stock http.server does not implement HTTP Range, which breaks <video> seeking
in the browser. This one serves the project directory and answers 206 partial
content requests properly.
"""
from __future__ import annotations

import os
import re
import sys
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent  # the project directory
PORT = int(os.environ.get("PORT", "8080"))
RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")


class Handler(BaseHTTPRequestHandler):
    server_version = "OpenMontagePreview/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # quieter logs
        sys.stderr.write("  %s %s\n" % (self.address_string(), fmt % args))

    def _resolve(self) -> Path | None:
        path = unquote(urlparse(self.path).path)
        if path in ("/", ""):
            path = "/preview/index.html"
        target = (ROOT / path.lstrip("/")).resolve()
        if not str(target).startswith(str(ROOT)):
            return None
        if target.is_dir():
            target = target / "preview" / "index.html" if (target / "preview").exists() else target / "index.html"
        return target

    def _send_headers(self, status, ctype, length, extra=None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()

    def do_HEAD(self):
        self._serve(head=False)

    def do_GET(self):
        self._serve(head=True)

    def _serve(self, head=True):
        target = self._resolve()
        if target is None or not target.is_file():
            body = b"404 not found\n"
            self._send_headers(404, "text/plain; charset=utf-8", len(body))
            if head:
                self.wfile.write(body)
            return

        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        size = target.stat().st_size
        rng = self.headers.get("Range")

        if rng:
            m = RANGE_RE.match(rng.strip())
            if not m:
                self._send_headers(416, "text/plain; charset=utf-8", 0,
                                   {"Content-Range": f"bytes */{size}"})
                return
            start = int(m.group(1)) if m.group(1) else 0
            end = int(m.group(2)) if m.group(2) else size - 1
            end = min(end, size - 1)
            if start > end or start >= size:
                self._send_headers(416, "text/plain; charset=utf-8", 0,
                                   {"Content-Range": f"bytes */{size}"})
                return
            length = end - start + 1
            self._send_headers(206, ctype, length,
                               {"Content-Range": f"bytes {start}-{end}/{size}"})
            if head:
                with target.open("rb") as fh:
                    fh.seek(start)
                    remaining = length
                    while remaining > 0:
                        chunk = fh.read(min(262144, remaining))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
            return

        self._send_headers(200, ctype, size)
        if head:
            with target.open("rb") as fh:
                while True:
                    chunk = fh.read(262144)
                    if not chunk:
                        break
                    self.wfile.write(chunk)


def main():
    mimetypes.add_type("video/mp4", ".mp4")
    mimetypes.add_type("video/webm", ".webm")
    mimetypes.add_type("font/ttf", ".ttf")
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"agents-make-video preview  ->  http://0.0.0.0:{PORT}/  (root: {ROOT})", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
