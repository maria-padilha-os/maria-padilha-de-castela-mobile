#!/usr/bin/env python3
"""Serve the Padilha preview locally for a stock GrapheneOS device or emulator.

The server is read-only, binds to loopback by default, and never needs root. It
serves the checkout so the preview can reach both ``preview/`` and ``assets/``.
"""

from __future__ import annotations

import argparse
import http.server
import pathlib
import sys
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
DENY_PARTS = {
    ".git",
    ".scratch",
    ".gradle",
    "keys",
    "signing",
    "secrets",
    "releases",
    "artifacts",
    "out",
    "build",
}
DENY_SUFFIXES = {
    ".apk",
    ".aab",
    ".apks",
    ".jks",
    ".keystore",
    ".p12",
    ".pfx",
    ".pk8",
    ".pem",
}


class PreviewHandler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".webmanifest": "application/manifest+json",
        ".webp": "image/webp",
        ".woff2": "font/woff2",
        ".svg": "image/svg+xml",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        parts = set(parsed.path.split("/"))
        if parts & DENY_PARTS or pathlib.PurePosixPath(parsed.path).suffix.lower() in DENY_SUFFIXES:
            self.send_error(404)
            return
        if parsed.path in {"", "/"}:
            self.send_response(302)
            self.send_header("Location", "/preview/")
            self.end_headers()
            return
        super().do_GET()

    def log_message(self, format, *args):
        sys.stderr.write(f"preview: {self.address_string()} {format % args}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default="127.0.0.1", help="address to listen on (default: loopback)")
    parser.add_argument("--port", type=int, default=8099)
    args = parser.parse_args(argv)

    if args.bind not in {"127.0.0.1", "::1", "localhost"}:
        print(
            "warning: this preview has no authentication; do not expose it to an untrusted network",
            file=sys.stderr,
        )

    server = http.server.ThreadingHTTPServer((args.bind, args.port), PreviewHandler)
    print(f"Padilha preview: http://{args.bind}:{args.port}/preview/")
    print("Read-only local server. No root, no system-partition access, no telemetry.")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
