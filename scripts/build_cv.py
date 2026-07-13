#!/usr/bin/env python3
"""Generate the data-driven sections of the LaTeX CVs from data/*.yaml.

Writes one fragment per section into cv/generated/; the hand-maintained
variant shells (cv/cv.tex, cv/publist.tex, ...) \\input the fragments they
want.  Fields the CV understands beyond what the website uses:

  papers.yaml:   cv: false        exclude from the CV
                 cv_section: publications   force an arXiv-only paper into
                                            the Publications section
                 title_tex: ...   LaTeX title override when the automatic
                                  mathification isn't right
  talks.yaml:    cv: false, cv_venue: short venue name
  software.yaml: cv: false, cv_only: true (CV but not website), cv_note

Usage: .venv/bin/python scripts/build_cv.py
"""

import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"
OUT = REPO / "cv" / "generated"
SITE_ROOT = "https://math.mit.edu/~roed"

MONTHS = {m[:3].lower(): m[:3] for m in
          ["January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"]}


def absurl(url):
    return SITE_ROOT + url if url.startswith("/") else url


def escape(text):
    """Escape LaTeX specials in plain text (not urls)."""
    return (text.replace("\\", r"\textbackslash{}").replace("&", r"\&")
                .replace("%", r"\%").replace("#", r"\#").replace("$", r"\$")
                .replace("_", r"\_"))


def mathify(text):
    """Turn the plain-text math idioms used in the yaml into LaTeX."""
    text = escape(text)
    text = re.sub(r"\bp-adic", r"$p$-adic", text)
    text = re.sub(r"\bp-Adic", r"$p$-Adic", text)
    text = re.sub(r"\bL-function", r"$L$-function", text)
    text = re.sub(r"\bL-packets", r"$L$-packets", text)
    text = text.replace("ℚ₂", r"$\mathbb{Q}_2$").replace("ℓ", r"$\ell$")
    text = text.replace("GL(2, Zhat)", r"$\mathrm{GL}(2,\widehat{\mathbb{Z}})$")
    return text


def html2latex(html):
    """Convert the constrained HTML used in yaml values to LaTeX."""
    out = []
    pos = 0
    # <a href="URL">TEXT</a> -> \bluelink{TEXT}{URL}
    for m in re.finditer(r'<a href="([^"]+)">(.*?)</a>', html, re.S):
        out.append(mathify(html[pos:m.start()]))
        url = absurl(m.group(1)).replace("%", r"\%").replace("#", r"\#")
        out.append(r"\bluelink{%s}{%s}" % (mathify(m.group(2)), url))
        pos = m.end()
    out.append(mathify(html[pos:]))
    text = "".join(out)
    text = re.sub(r"</?b>", lambda m: "}" if m.group(0)[1] == "/" else r"\textbf{", text)
    text = re.sub(r"</?i>", lambda m: "}" if m.group(0)[1] == "/" else r"\textit{", text)
    text = re.sub(r'<span title="[^"]*">(.*?)</span>', r"\1", text, flags=re.S)
    text = re.sub(r"<[^>]+>", "", text)  # anything else: strip tags
    return text


def month_year(datestr, year=None):
    """'April 2, 9, 16, 2010' -> 'Apr 2010'; ('February 23-27', 2026) -> 'Feb 2026'."""
    if year is None:
        m = re.search(r"(\d{4})\s*$", datestr)
        year = m.group(1) if m else ""
    mon = ""
    m = re.match(r"\s*([A-Za-z]+)", datestr)
    if m:
        mon = MONTHS.get(m.group(1)[:3].lower(), m.group(1)[:3])
    return f"{mon} {year}".strip()


def authors_line(paper):
    """Full author list in reading order, from bibtex when available."""
    bib = (paper.get("bibtex") or {}).get("fields", {})
    if bib.get("author"):
        names = []
        for name in bib["author"].split(" and "):
            if "," in name:
                last, first = name.split(",", 1)
                names.append(f"{first.strip()} {last.strip()}")
            else:
                names.append(name.strip())
    else:
        names = list(paper.get("with") or []) + ["David Roe"]
        names.sort(key=lambda n: n.split()[-1])
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " and " + names[-1]


def title_link(paper):
    if paper.get("doi"):
        return paper["doi"]
    if paper.get("arxiv"):
        return f"https://arxiv.org/abs/{paper['arxiv']}"
    if paper.get("pdf"):
        return absurl(paper["pdf"])
    return None


def paper_line(paper, preprint):
    title = paper.get("title_tex") or mathify(paper["title"])
    url = title_link(paper)
    linked = r"\bluelink{%s}{%s}" % (title, url) if url else title
    parts = [f"{escape(authors_line(paper))}, {linked}"]
    status = paper.get("status", "")
    if preprint:
        if paper.get("arxiv"):
            parts.append(f"arXiv:{paper['arxiv']}")
        if status and status.lower() != "preprint":
            parts.append(html2latex(status))
    elif status:
        parts.append(html2latex(status))
    return r"\cvline{}{%s.}" % ", ".join(p.rstrip(".") for p in parts)


def is_preprint(paper):
    if paper.get("cv_section") == "publications":
        return False
    status = re.sub(r"<[^>]+>", "", paper.get("status", "")).strip()
    return (not status) or bool(re.match(r"^(Preprint|Submitted|Accepted)", status))


def gen_publications(papers):
    arts = [p for p in papers["articles"] if p.get("cv", True)]
    theses = [p for p in papers["theses"] if p.get("cv", True)]
    pre = [p for p in arts if is_preprint(p)]
    pub = [p for p in arts if not is_preprint(p)]
    lines = [r"\section{\textsc{Preprints}}", ""]
    lines += [paper_line(p, True) + "\n" for p in pre]
    lines += [r"\section{\textsc{Publications}}", ""]
    lines += [paper_line(p, False) + "\n" for p in pub]
    lines += [paper_line(p, False) + "\n" for p in theses]
    return "\n".join(lines)


def gen_talks(talks):
    rows = []
    for t in talks:
        if not t.get("cv", True):
            continue
        title = t.get("title_tex") or mathify(t["title"])
        venue = escape(t.get("cv_venue") or t.get("venue", ""))
        rows.append((month_year(t["date"]), f"{title} ({venue})" if venue else title))
    lines = [r"\goodindentsection{\textsc{Invited Talks}}{%s}{%s}" % rows[0], ""]
    lines += [r"\cvlinesm{%s}{%s}" % r + "\n" for r in rows[1:]]
    return "\n".join(lines)


def gen_conferences_organized(conferences):
    rows = []
    for c in conferences:
        if c.get("role") != "organizer":
            continue
        name = mathify(c["name"])
        if c.get("url"):
            url = absurl(c["url"]).replace("%", r"\%").replace("#", r"\#")
            name = r"\bluelink{%s}{%s}" % (name, url)
        rows.append((month_year(c["dates"], c["year"]), f"{name} ({escape(c['location'])})"))
    lines = [r"\goodindentsection{\textsc{Conferences Organized}}{%s}{%s}" % rows[0], ""]
    lines += [r"\cvlinesm{%s}{%s}" % r + "\n" for r in rows[1:]]
    return "\n".join(lines)


def years(span):
    """'2020-2025' -> '2020--2025' (en dash), leave '2023, 2026' alone."""
    return re.sub(r"(\d{4})-(\d{4}|present)", r"\1--\2", str(span))


def cv_section(cv, name):
    return next(s for s in cv if s["section"] == name)


def rows_section(title, rows):
    """Render [(when, what), ...] as a goodindentsection + cvlinesm list."""
    lines = [r"\goodindentsection{\textsc{%s}}{%s}{%s}" % (title, rows[0][0], rows[0][1]), ""]
    lines += [r"\cvlinesm{%s}{%s}" % r + "\n" for r in rows[1:]]
    return "\n".join(lines)


def gen_awards(cv):
    sec = cv_section(cv, "Grants, Fellowships, and Awards")
    rows = [(years(r[-1]), html2latex(r[0])) for r in sec["rows"]]
    return rows_section("Grants, Fellowships, and Awards", rows)


def gen_editorial(cv):
    sec = cv_section(cv, "Editorial Positions")
    rows = [(years(r[2]), f"{html2latex(r[0])}, {html2latex(r[1])}") for r in sec["rows"]]
    return rows_section("Editorial Positions", rows)


def gen_other_activities(cv):
    sec = cv_section(cv, "Other Activities")
    rows = []
    for what, where, when in sec["rows"]:
        text = html2latex(what) + (f", {html2latex(where)}" if where else "")
        rows.append((years(when), text))
    return rows_section("Other Activities", rows)


def linklabel(url):
    return re.sub(r"^https?://(www\.)?", "", url).rstrip("/")


def gen_software(software):
    entries = []
    for sec in software:
        for pr in sec["projects"]:
            if not pr.get("cv", True):
                continue
            name = pr["name"]
            if sec["section"] == "Mathematical Databases" and name != "LMFDB":
                name = f"LMFDB: {name}"
            elif name == "LMFDB":
                name = "L-functions and Modular Forms Database (LMFDB)"
            links = pr.get("links") or {}
            url = links.get("browse") or pr.get("url") or links.get("code", "")
            note = html2latex(pr["cv_note"]) if pr.get("cv_note") else ""
            entries.append((years(pr.get("active", "")), escape(name),
                            r"\bluelink{%s}{%s}" % (escape(linklabel(url)), url), note))
    y, name, link, note = entries[0]
    first = r"\cvline[-12pt]{%s}{\textbf{%s}, %s.%s}" % (
        y, name, link, r"{\newline{}\small %s}" % note if note else "")
    lines = [r"\section{\textsc{Software and Databases}}", r"\cvline{}{}", first, ""]
    for y, name, link, note in entries[1:]:
        lines.append(r"\cventry{%s}{%s}{}{%s}{}{%s}" % (y, name, link, note) + "\n")
    return "\n".join(lines)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    papers = yaml.safe_load(open(DATA / "papers.yaml"))
    talks = yaml.safe_load(open(DATA / "talks.yaml"))
    conferences = yaml.safe_load(open(DATA / "conferences.yaml"))
    cv = yaml.safe_load(open(DATA / "cv.yaml"))
    software = yaml.safe_load(open(DATA / "software.yaml"))
    fragments = {
        "publications.tex": gen_publications(papers),
        "talks.tex": gen_talks(talks),
        "conferences_organized.tex": gen_conferences_organized(conferences),
        "awards.tex": gen_awards(cv),
        "editorial.tex": gen_editorial(cv),
        "other_activities.tex": gen_other_activities(cv),
        "software.tex": gen_software(software),
    }
    header = "%% Generated by scripts/build_cv.py -- do not edit by hand.\n\n"
    for name, body in fragments.items():
        (OUT / name).write_text(header + body + "\n")
        print(f"  cv/generated/{name}")


if __name__ == "__main__":
    main()
