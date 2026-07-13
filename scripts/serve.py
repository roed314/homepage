#!/usr/bin/env python3
"""Serve site/ on port 8314 with caching disabled.

Plain `python -m http.server` sends no Cache-Control header, so browsers
apply heuristic caching and happily show stale pages after a rebuild --
"I rebuilt but the page didn't change" is almost always that.  This wrapper
adds Cache-Control: no-store so every reload reflects the current build.

Usage: .venv/bin/python scripts/serve.py [port]
"""

import functools
import http.server
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent / "site"


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8314
    handler = functools.partial(NoCacheHandler, directory=str(SITE))
    print(f"http://localhost:{port}/  (caching disabled)")
    http.server.ThreadingHTTPServer(("", port), handler).serve_forever()


if __name__ == "__main__":
    main()
