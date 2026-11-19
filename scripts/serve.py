#!/usr/bin/env python3
"""Serve site/ on port 8314 with caching disabled.

Plain `python -m http.server` sends no Cache-Control header, so browsers
apply heuristic caching and happily show stale pages after a rebuild --
"I rebuilt but the page didn't change" is almost always that.  This wrapper
adds Cache-Control: no-store so every reload reflects the current build.

Paths missing from site/ are looked up in ~/claude/current_homepage, the copy
of the server's web root.  deploy.sh overlays site/ on that tree without
--delete, so this is what the live site serves too: conferences/*/, courses/,
writings/ and other hand-maintained pages work locally.

Usage: .venv/bin/python scripts/serve.py [port]
"""

import functools
import http.server
import os
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent / "site"
WEBROOT = Path.home() / "claude" / "current_homepage"


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def translate_path(self, path):
        local = super().translate_path(path)
        if not os.path.exists(local):
            fallback = WEBROOT / os.path.relpath(local, self.directory)
            if fallback.exists():
                return str(fallback)
        return local


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8314
    handler = functools.partial(NoCacheHandler, directory=str(SITE))
    print(f"http://localhost:{port}/  (caching disabled)")
    http.server.ThreadingHTTPServer(("", port), handler).serve_forever()


if __name__ == "__main__":
    main()
