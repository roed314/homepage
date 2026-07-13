#!/usr/bin/env python3
"""Populate bibtex metadata in data/papers.yaml from DOI content negotiation.

For each article, fetches BibTeX from doi.org (using the paper's DOI, or its
arXiv DOI 10.48550/arXiv.<id> when only an arXiv id is available), parses the
fields, and stores them under a `bibtex:` key.  Entries that already have
`bibtex:` are skipped unless --refresh is given.  build.py renders the stored
fields into .bib files; this script is only needed when adding papers.

Usage: .venv/bin/python scripts/fetch_bibtex.py [--refresh]
"""

import re
import sys
import time
import unicodedata
import urllib.request
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
PAPERS = REPO / "data" / "papers.yaml"

FIELD_RE = re.compile(r"(\w+)\s*=\s*\{((?:[^{}]|\{[^{}]*\})*)\}")
HEAD_RE = re.compile(r"@(\w+)\s*\{\s*([^,\s]+)\s*,")


def fetch(url):
    req = urllib.request.Request(url, headers={
        "Accept": "application/x-bibtex",
        "User-Agent": "roed-homepage-bib (roed@mit.edu)",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


# Crossref/DataCite responses sometimes contain Unicode that pdflatex cannot
# digest (mathematical-alphanumeric letters, primes).  Latin-1 accents,
# en-dashes and curly quotes are fine and left alone.
MATH_ALNUM = re.compile(r"[\U0001D400-\U0001D7FF]")


def sanitize(value):
    value = MATH_ALNUM.sub(lambda m: "$%s$" % unicodedata.normalize("NFKC", m.group(0)), value)
    return value.replace("′", "'").replace("″", "''")


def protect(title):
    """Brace-protect capitals in a title so bibtex case-folding keeps them."""
    out = []
    for i, w in enumerate(title.split(" ")):
        if "{" in w or "$" in w:
            out.append(w)
        elif re.search(r"[A-ZÀ-Þ]", w[1:]) or (i > 0 and w[:1].isupper()):
            m = re.match(r"^(.*?)([,:.;]*)$", w)
            out.append("{%s}%s" % (m.group(1), m.group(2)))
        else:
            out.append(w)
    return " ".join(out)


def parse(bib):
    head = HEAD_RE.search(bib)
    if not head:
        return None
    fields = {}
    for name, value in FIELD_RE.findall(bib):
        value = sanitize(re.sub(r"\s+", " ", value).strip())
        if name.lower() == "title":
            value = protect(value)
        fields[name.lower()] = value
    return {"type": head.group(1).lower(), "key": head.group(2), "fields": fields}


def doi_url(paper):
    doi = paper.get("doi", "")
    if re.match(r"https?://(dx\.)?doi\.org/10\.", doi):
        return doi
    if paper.get("arxiv"):
        return f"https://doi.org/10.48550/arXiv.{paper['arxiv']}"
    return None


def main():
    refresh = "--refresh" in sys.argv
    data = yaml.safe_load(open(PAPERS))
    seen_keys = set()
    failures = 0
    for paper in data["articles"] + data["theses"]:
        existing = paper.get("bibtex")
        if existing and not refresh:
            seen_keys.add(existing["key"])
            continue
        url = doi_url(paper)
        if not url:
            print(f"  skip (no doi/arxiv): {paper['title'][:60]}")
            continue
        try:
            entry = parse(fetch(url))
        except Exception as e:
            print(f"  FAILED {url}: {e}")
            failures += 1
            continue
        if not entry:
            print(f"  FAILED to parse bibtex from {url}")
            failures += 1
            continue
        # keys must be unique across the bibliography
        key = entry["key"]
        while key in seen_keys:
            key += "a"
        entry["key"] = key
        seen_keys.add(key)
        paper["bibtex"] = entry
        print(f"  {entry['type']:8s} {key:28s} {paper['title'][:48]}")
        time.sleep(0.5)
    with open(PAPERS, "w") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False, width=10000)
    print(f"wrote {PAPERS.relative_to(REPO)}" + (f" ({failures} failures)" if failures else ""))


if __name__ == "__main__":
    main()
