#!/usr/bin/env python3
"""Refresh the per-project contribution figures in data/software.yaml.

For every project whose code link points at github.com, queries the GitHub
contributor-stats API for roed314's commits, additions and deletions, and the
first/last year of activity, then writes the numbers back to software.yaml.

Caveats handled gracefully (old numbers are kept and a warning printed):
  - the stats endpoint only reports the top 100 contributors per repo, so
    very large repos (e.g. sagemath/sage) may not include roed314;
  - GitHub returns 202 while it computes stats: we retry a few times;
  - network/rate-limit failures.

A token raises the rate limit and is taken from $GITHUB_TOKEN or `gh auth
token` when available; anonymous access works fine for occasional use.

Usage: .venv/bin/python scripts/github_stats.py
Exits 0 even on partial failure (so `make deploy` is never blocked); pass
--strict to exit 1 if any repo could not be refreshed.
"""

import datetime
import json
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import yaml

LOGIN = "roed314"
REPO = Path(__file__).resolve().parent.parent
SOFTWARE = REPO / "data" / "software.yaml"


def token():
    import os
    if os.environ.get("GITHUB_TOKEN"):
        return os.environ["GITHUB_TOKEN"]
    try:
        t = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=10)
        if t.returncode == 0 and t.stdout.strip():
            return t.stdout.strip()
    except Exception:
        pass
    return None


def contributor_stats(owner, repo, tok):
    url = f"https://api.github.com/repos/{owner}/{repo}/stats/contributors"
    headers = {"Accept": "application/vnd.github+json",
               "User-Agent": "roed-homepage-stats"}
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    for attempt in range(6):
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as r:
            if r.status == 202:          # stats being computed; try again
                time.sleep(4)
                continue
            return json.load(r)
    return None


def main():
    strict = "--strict" in sys.argv
    tok = token()
    data = yaml.safe_load(open(SOFTWARE))
    failures = []
    for sec in data:
        for pr in sec["projects"]:
            code = (pr.get("links") or {}).get("code", "")
            m = re.search(r"github\.com/([^/]+)/([^/]+)", code)
            if not m:
                continue
            owner, repo = m.group(1), m.group(2)
            try:
                stats = contributor_stats(owner, repo, tok)
            except Exception as e:
                print(f"  {pr['name']}: FAILED ({e}); keeping old numbers")
                failures.append(pr["name"])
                continue
            mine = next((c for c in (stats or [])
                         if (c.get("author") or {}).get("login", "").lower() == LOGIN), None)
            if not mine:
                print(f"  {pr['name']}: {LOGIN} not in top-100 contributors of "
                      f"{owner}/{repo}; keeping old numbers")
                failures.append(pr["name"])
                continue
            active_weeks = [w for w in mine["weeks"] if w["c"]]
            years = [datetime.date.fromtimestamp(w["w"]).year for w in active_weeks]
            old = (pr.get("active"), pr.get("commits"))
            # a `since:` field pins the start year for involvement that predates
            # the repo's git history (svn/hg era, or commits under other emails)
            start = pr.get("since", min(years))
            pr["active"] = f"{start}-{max(years)}"
            pr["commits"] = f"{mine['total']:,}"
            adds = sum(w["a"] for w in mine["weeks"])
            dels = sum(w["d"] for w in mine["weeks"])
            if adds or dels:
                pr["additions"] = f"{adds:,}"
                pr["deletions"] = f"{dels:,}"
            else:
                # GitHub omits line counts for repos with >10k commits (the
                # weeks all come back a=0, d=0); keep the stored numbers,
                # which are computed by other means (e.g. git log --numstat
                # on a local clone) rather than overwriting them with zeros.
                print(f"  {pr['name']}: no line counts from GitHub; keeping stored additions/deletions")
            print(f"  {pr['name']}: {old[0]} · {old[1]}  ->  {pr['active']} · {pr['commits']}")
    with open(SOFTWARE, "w") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False, width=10000)
    print(f"wrote {SOFTWARE.relative_to(REPO)}"
          + (f"  ({len(failures)} kept old numbers: {', '.join(failures)})" if failures else ""))
    return 1 if (strict and failures) else 0


if __name__ == "__main__":
    sys.exit(main())
