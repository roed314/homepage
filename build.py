#!/usr/bin/env python3
"""Static site builder: data/*.yaml + templates/ -> site/

Usage: python build.py            (or `make build`)

Every internal link in data files and templates is written site-root-relative
(leading slash, e.g. /writings/talks/foo.pdf).  At render time the |u filter
(for single urls) and |rel filter (for embedded HTML) convert these to paths
relative to the page being rendered, so the site works both at
http://localhost:8314/ and https://math.mit.edu/~roed/ without configuration.
"""

import datetime
import re
import shutil
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, pass_context

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SITE = ROOT / "site"
STATIC = ROOT / "static"

# ------------------------------------------------------------------ nav model

# section id -> (label, landing path, groups of subpages)
# Groups render as visually separated lists in the sidebar, as on the old site.
SECTIONS = {
    "research": {
        "label": "Research",
        "path": "/papers/",
        "groups": [
            [("papers", "/papers/", "Publications"),
             ("software", "/software/", "Software"),
             ("talks", "/talks/", "Talks"),
             ("conferences", "/conferences/", "Conferences")],
            [("cv", "/cv/", "CV"),
             ("students", "/students/", "Students"),
             ("interests", "/interests/", "Interests")],
        ],
    },
    "teaching": {
        "label": "Teaching",
        "path": "/teaching/",
        "groups": [
            [("courses", "/teaching/", "Courses"),
             ("resources", "/resources/", "Resources")],
        ],
    },
    "other": {
        "label": "Other",
        "path": "/padicts/",
        "groups": [
            [("padicts", "/padicts/", "Society of p-adicts")],
        ],
    },
}

# path, template, section id, subpage id, title
PAGES = [
    ("", "home.html", None, None, None),
    ("papers/", "papers.html", "research", "papers", "Publications"),
    ("software/", "software.html", "research", "software", "Software"),
    ("talks/", "talks.html", "research", "talks", "Talks"),
    ("conferences/", "conferences.html", "research", "conferences", "Conferences"),
    ("cv/", "cv.html", "research", "cv", "Curriculum Vitae"),
    ("students/", "students.html", "research", "students", "Student Research"),
    ("interests/", "interests.html", "research", "interests", "Interests"),
    ("teaching/", "teaching.html", "teaching", "courses", "Courses"),
    ("resources/", "resources.html", "teaching", "resources", "Resources"),
    ("padicts/", "padicts.html", "other", "padicts", "Society of p-adicts"),
    ("contact/", "contact.html", None, None, "Contact"),
]


# ------------------------------------------------------------------ url helpers

@pass_context
def relurl(ctx, target):
    """Convert a site-root-relative url (/x/y) to one relative to this page."""
    if not target.startswith("/"):
        return target
    prefix = "../" * ctx["page"]["depth"]
    rel = prefix + target[1:]
    return rel or "./"


@pass_context
def relhtml(ctx, html):
    """Rewrite href="/..." and src="/..." in an HTML string relative to this page."""
    prefix = "../" * ctx["page"]["depth"]

    def fix(m):
        return f'{m.group(1)}="{prefix}{m.group(2)}"'

    return re.sub(r'(href|src)="/([^"]*)"', fix, html)


# ------------------------------------------------------------------ dates

MONTHS = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june",
     "july", "august", "september", "october", "november", "december"])}
for m in list(MONTHS):
    MONTHS[m[:3]] = MONTHS[m]


def conf_start(conf):
    """Best-effort start date of a conference from its dates + year fields."""
    m = re.match(r"([A-Za-z]+)\.?\s+(\d+)", conf.get("dates", ""))
    if not m:
        return None
    month = MONTHS.get(m.group(1).lower().rstrip("."))
    if not month:
        return None
    try:
        return datetime.date(conf["year"], month, int(m.group(2)))
    except ValueError:
        return None


def talk_date(talk):
    s = talk.get("date", "")
    m = re.match(r"([A-Za-z]+)\.?\s+(\d+),?\s+(\d{4})", s)
    if not m:
        return None
    month = MONTHS.get(m.group(1).lower().rstrip("."))
    if not month:
        return None
    try:
        return datetime.date(int(m.group(3)), month, int(m.group(2)))
    except ValueError:
        return None


# ------------------------------------------------------------------ bibtex

# preferred field order in rendered entries; anything else follows alphabetically
BIB_ORDER = ["author", "title", "journal", "booktitle", "series", "volume",
             "number", "pages", "year", "month", "publisher", "school",
             "eprint", "archiveprefix", "primaryclass", "doi", "url"]
BIB_SKIP = {"copyright", "keywords", "issn", "isbn"}


def render_bib(paper):
    """Render one paper's stored bibtex fields as a BibTeX entry."""
    bib = paper["bibtex"]
    fields = dict(bib["fields"])
    if paper.get("arxiv") and "eprint" not in fields:
        fields["eprint"] = paper["arxiv"]
        fields["archiveprefix"] = "arXiv"
    keys = [k for k in BIB_ORDER if k in fields]
    keys += sorted(k for k in fields if k not in BIB_ORDER and k not in BIB_SKIP)
    lines = [f"@{bib['type']}{{{bib['key']},"]
    lines += [f"  {k} = {{{fields[k]}}}," for k in keys]
    lines.append("}")
    return "\n".join(lines)


def write_bibs(data):
    bibdir = SITE / "bib"
    bibdir.mkdir()
    combined = []
    for paper in data["papers"]["articles"] + data["papers"]["theses"]:
        if not paper.get("bibtex"):
            continue
        entry = render_bib(paper)
        (bibdir / f"{paper['bibtex']['key']}.bib").write_text(entry + "\n")
        combined.append(entry)
    (bibdir / "roe.bib").write_text("\n\n".join(combined) + "\n")
    print(f"  site/bib/ ({len(combined)} entries)")


# ------------------------------------------------------------------ build

def load_data():
    data = {}
    for f in DATA.glob("*.yaml"):
        with open(f) as fh:
            data[f.stem] = yaml.safe_load(fh)
    return data


def main():
    data = load_data()
    today = datetime.date.today()

    # derived collections for the landing page
    confs = data.get("conferences", [])
    for c in confs:
        c["start"] = conf_start(c)
    upcoming = sorted([c for c in confs if c["start"] and c["start"] >= today],
                      key=lambda c: c["start"])
    past = [c for c in confs if c not in upcoming]
    derived = {
        "recent_papers": data["papers"]["articles"][:3],
        "recent_talks": data["talks"][:3],
        "upcoming_conferences": upcoming,
        "recent_conferences": past[:3],
        "recent_courses": data["courses"][:2],
        # first project of each software section, for the landing page
        "featured_software": [s["projects"][0] for s in data["software"] if s.get("projects")],
        # cv's "Conferences Organized" section is derived, not duplicated
        "organized_conferences": [c for c in confs if c.get("role") == "organizer"],
        "today": today,
    }

    env = Environment(
        loader=FileSystemLoader(ROOT / "templates"),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["u"] = relurl
    env.filters["rel"] = relhtml

    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir()

    for path, template, section, subpage, title in PAGES:
        page = {
            "path": "/" + path,
            "depth": path.count("/"),
            "section": section,
            "subpage": subpage,
            "title": title,
        }
        ctx = dict(data)
        ctx.update(derived)
        ctx.update(page=page, sections=SECTIONS)
        html = env.get_template(template).render(**ctx)
        out = SITE / path / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html)
        print(f"  {out.relative_to(ROOT)}")

    write_bibs(data)

    # static assets
    for sub in ("css", "js", "pics", "writings"):
        src = STATIC / sub
        if src.exists():
            shutil.copytree(src, SITE / sub)
    fav = STATIC / "favicon.ico"
    if fav.exists():
        shutil.copy(fav, SITE / "favicon.ico")
    print(f"built {len(PAGES)} pages -> {SITE.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
