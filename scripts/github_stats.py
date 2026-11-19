#!/usr/bin/env python3
"""Refresh the per-project contribution figures in data/software.yaml.

For every project whose code link points at github.com, computes commits,
additions, deletions and the first/last year of activity, and writes them
back to software.yaml.

Contributions are split between two GitHub accounts: roed314 (written by
hand) and roed-math (written by AI agents; the account was created on
2026-05-14).  Since then, commits linked to roed-math (roed314@gmail.com)
are AI.  Those linked to roed314 (roed.math@gmail.com) are ambiguous, since
both accounts commit with that email, and are credited to the account they
came in through:

  1. the author of a merged pull request (by either account) containing it;
  2. otherwise, the account that pushed it to the default branch, from the
     repository activity API;
  3. otherwise, roed314.

Older commits are all hand-written.  A project with any AI commits gets an
`ai:` block (commits/additions/deletions), and its top-level figures count
the hand-written commits only; both come from the GraphQL commit history and
exclude merge commits, as GitHub's contributors graph does.  Projects
without AI commits keep the contributor-stats figures for roed314.

A project may list `repos:` (owner/name, the code link's repo included) to
sum its figures over several repositories, each split as above.

Caveats handled gracefully (old numbers are kept and a warning printed):
  - the contributor-stats endpoint only reports the top 100 contributors per
    repo, so very large repos (e.g. sagemath/sage) may not include roed314;
  - GitHub returns 202 while it computes stats: we retry a few times;
  - network/rate-limit failures.

A token raises the rate limit and is taken from $GITHUB_TOKEN or `gh auth
token` when available.  GraphQL needs one; without it AI attribution is
skipped and every project keeps the contributor-stats path.

Usage: .venv/bin/python scripts/github_stats.py
Exits 0 even on partial failure (so `make deploy` is never blocked); pass
--strict to exit 1 if any repo could not be refreshed.
"""

import datetime
import http.client
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import yaml

LOGIN = "roed314"
AI_LOGIN = "roed-math"
AI_SINCE = "2026-05-14T00:00:00Z"
ACCOUNTS = (LOGIN, AI_LOGIN)
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


def headers(tok):
    h = {"Accept": "application/vnd.github+json", "User-Agent": "roed-homepage-stats"}
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


def rest(path, tok):
    return rest_with_next(f"https://api.github.com/{path}", tok)[0]


def rest_with_next(url, tok):
    req = urllib.request.Request(url, headers=headers(tok))
    with urllib.request.urlopen(req, timeout=60) as r:
        m = re.search(r'<([^>]+)>;\s*rel="next"', r.headers.get("Link", ""))
        return json.load(r), (m.group(1) if m else None)


def rest_pages(path, tok, limit=50):
    # follows Link headers: the activity API pages by cursor, not page number
    sep = "&" if "?" in path else "?"
    url = f"https://api.github.com/{path}{sep}per_page=100"
    for _ in range(limit):
        batch, url = rest_with_next(url, tok)
        yield from batch
        if not url:
            return


def graphql(query, variables, tok):
    body = json.dumps({"query": query, "variables": variables}).encode()
    for attempt in range(4):
        req = urllib.request.Request("https://api.github.com/graphql", data=body,
                                     headers=headers(tok), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                out = json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 503 and attempt < 3:
                time.sleep(5)
                continue
            raise
        except (urllib.error.URLError, ConnectionError, http.client.HTTPException):
            # deep history pages on large repos often drop the connection
            if attempt < 3:
                time.sleep(5)
                continue
            raise
        if out.get("errors"):
            raise RuntimeError(out["errors"][0].get("message", out["errors"]))
        return out["data"]


def contributor_stats(owner, repo, tok):
    url = f"https://api.github.com/repos/{owner}/{repo}/stats/contributors"
    for attempt in range(6):
        req = urllib.request.Request(url, headers=headers(tok))
        with urllib.request.urlopen(req, timeout=60) as r:
            if r.status == 202:          # stats being computed; try again
                time.sleep(4)
                continue
            return json.load(r)
    return None


HISTORY = """
query($owner: String!, $name: String!, $id: ID!, $since: GitTimestamp,
      $until: GitTimestamp, $after: String, $prs: Boolean!, $first: Int!) {
  repository(owner: $owner, name: $name) {
    defaultBranchRef { name target { ... on Commit {
      history(first: $first, after: $after, author: {id: $id}, since: $since, until: $until) {
        pageInfo { hasNextPage endCursor }
        nodes {
          oid authoredDate additions deletions parents { totalCount }
          associatedPullRequests(first: 10) @include(if: $prs) {
            nodes { merged mergedAt author { login } }
          }
        }
      }
    } } }
  }
}"""


def history(owner, repo, user_id, tok, since=None, until=None, prs=False):
    """Non-merge commits on the default branch authored by user_id."""
    commits, after, branch = [], None, None
    first = 100
    while True:
        try:
            data = graphql(HISTORY, {"owner": owner, "name": repo, "id": user_id, "since": since,
                                     "until": until, "after": after, "prs": prs, "first": first}, tok)
        except urllib.error.HTTPError as e:
            # pull-request lookups on very large repos (TauCeti) time out at 100 per page
            if e.code in (502, 504) and first > 10:
                first //= 2
                continue
            raise
        ref = data["repository"]["defaultBranchRef"]
        branch = ref["name"]
        h = ref["target"]["history"]
        commits += [c for c in h["nodes"] if c["parents"]["totalCount"] == 1]
        if not h["pageInfo"]["hasNextPage"]:
            return branch, commits
        after = h["pageInfo"]["endCursor"]


def pushers(owner, repo, branch, tok):
    """sha -> account, for commits either account pushed to the default branch."""
    out = {}
    events = []
    for actor in ACCOUNTS:
        events += [e for e in rest_pages(f"repos/{owner}/{repo}/activity?ref={branch}&actor={actor}", tok)
                   if e["activity_type"] in ("push", "force_push", "branch_creation")
                   and e["timestamp"] >= AI_SINCE]
    for e in sorted(events, key=lambda e: e["timestamp"]):
        actor = e["actor"]["login"]
        try:
            if set(e["before"]) == {"0"}:      # the default branch itself was created
                shas = [c["sha"] for c in rest_pages(
                    f"repos/{owner}/{repo}/commits?sha={e['after']}&since={AI_SINCE}", tok)]
            else:
                cmp = rest(f"repos/{owner}/{repo}/compare/{e['before']}...{e['after']}", tok)
                shas = [c["sha"] for c in cmp["commits"]]
        except urllib.error.HTTPError:          # e.g. a force-push whose old head is gone
            continue
        for sha in shas:
            out.setdefault(sha, actor)
    return out


def own_prs(commit):
    return [p for p in commit["associatedPullRequests"]["nodes"]
            if p["merged"] and (p["author"] or {}).get("login") in ACCOUNTS]


def origin(commit, pushed):
    prs = own_prs(commit)
    if prs:
        return min(prs, key=lambda p: p["mergedAt"])["author"]["login"]
    return pushed.get(commit["oid"], LOGIN)


def split_stats(owner, repo, ids, tok, need_ai=True):
    """Totals per account, or None when need_ai and the repo has no AI commits."""
    # Only commits linked to roed314 (i.e. roed.math@gmail.com) are ambiguous;
    # pull-request lookups are slow on large repos, so commits linked to
    # roed-math are credited to it directly.
    branch, ambiguous = history(owner, repo, ids[LOGIN], tok, since=AI_SINCE, prs=True)
    ai_linked = history(owner, repo, ids[AI_LOGIN], tok, since=AI_SINCE)[1]
    pushed = {}
    if any(not own_prs(c) for c in ambiguous):
        pushed = pushers(owner, repo, branch, tok)
    tally = {a: {"commits": 0, "additions": 0, "deletions": 0} for a in ACCOUNTS}
    years = []
    seen = set()

    def add(account, c):
        if c["oid"] in seen:
            return
        seen.add(c["oid"])
        t = tally[account]
        t["commits"] += 1
        t["additions"] += c["additions"]
        t["deletions"] += c["deletions"]
        years.append(int(c["authoredDate"][:4]))

    for c in ambiguous:
        add(origin(c, pushed), c)
    for c in ai_linked:
        add(AI_LOGIN, c)
    if need_ai and not tally[AI_LOGIN]["commits"]:
        return None
    for uid in ids.values():
        for c in history(owner, repo, uid, tok, until=AI_SINCE)[1]:
            add(LOGIN, c)
    return tally, years


def combined_stats(repos, ids, tok):
    """split_stats summed over several repos."""
    tally = {a: {"commits": 0, "additions": 0, "deletions": 0} for a in ACCOUNTS}
    years = []
    for owner, repo in repos:
        t, y = split_stats(owner, repo, ids, tok, need_ai=False)
        for a in ACCOUNTS:
            for k in tally[a]:
                tally[a][k] += t[a][k]
        years += y
    return tally, years


def fmt(n):
    return f"{n:,}"


def main():
    strict = "--strict" in sys.argv
    tok = token()
    ids = {}
    if tok:
        try:
            ids = {a: rest(f"users/{a}", tok)["node_id"] for a in ACCOUNTS}
        except Exception as e:
            print(f"  could not look up account ids ({e}); skipping AI attribution")
    data = yaml.safe_load(open(SOFTWARE))
    failures = []
    for sec in data:
        for pr in sec["projects"]:
            code = (pr.get("links") or {}).get("code", "")
            m = re.search(r"github\.com/([^/]+)/([^/]+)", code)
            if not m:
                continue
            owner, repo = m.group(1), m.group(2)
            repos = [r.split("/") for r in pr.get("repos", [])]
            old = (pr.get("active"), pr.get("commits"), (pr.get("ai") or {}).get("commits"))
            split = None
            if ids:
                try:
                    if repos:
                        split = combined_stats(repos, ids, tok)
                    else:
                        split = split_stats(owner, repo, ids, tok)
                except Exception as e:
                    print(f"  {pr['name']}: AI attribution FAILED ({e}); keeping old numbers")
                    failures.append(pr["name"])
                    continue
            if split:
                tally, years = split
                human, ai = tally[LOGIN], tally[AI_LOGIN]
                pr["active"] = f"{pr.get('since', min(years))}-{max(years)}"
                pr["commits"] = fmt(human["commits"])
                pr["additions"] = fmt(human["additions"])
                pr["deletions"] = fmt(human["deletions"])
                if ai["commits"]:
                    pr["ai"] = {k: fmt(v) for k, v in ai.items()}
                else:
                    pr.pop("ai", None)
                print(f"  {pr['name']}: {old[0]} · {old[1]} (AI {old[2]})  ->  "
                      f"{pr['active']} · {pr['commits']} (AI {fmt(ai['commits'])})")
                continue
            pr.pop("ai", None)
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
            # a `since:` field pins the start year for involvement that predates
            # the repo's git history (svn/hg era, or commits under other emails)
            start = pr.get("since", min(years))
            pr["active"] = f"{start}-{max(years)}"
            pr["commits"] = fmt(mine["total"])
            adds = sum(w["a"] for w in mine["weeks"])
            dels = sum(w["d"] for w in mine["weeks"])
            if adds or dels:
                pr["additions"] = fmt(adds)
                pr["deletions"] = fmt(dels)
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
