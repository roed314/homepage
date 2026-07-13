#!/usr/bin/env python3
"""One-time extraction of site data from the old single-page index.html.

Parses ~/claude/current_homepage/index.html (the last hand-edited version of
the old site) and writes:
  - data/*.yaml           structured data (papers, talks, conferences, ...)
  - templates/content/*.html   prose sections, normalized, as Jinja fragments

Internal links are rewritten to site-root-relative form (leading slash);
the build relativizes them per-page.  Kept in the repo for reference, but
after the initial migration the YAML files are the source of truth.
"""

import re
import sys
from pathlib import Path

import yaml
from bs4 import BeautifulSoup, NavigableString, Tag

OLD = Path.home() / "claude" / "current_homepage" / "index.html"
REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"
CONTENT = REPO / "templates" / "content"

# Old hash-navigation targets -> new page paths
HASH_MAP = {
    "#home": "/",
    "#research": "/papers/",
    "#research-papers": "/papers/",
    "#research-software": "/software/",
    "#research-talks": "/talks/",
    "#research-conferences": "/conferences/",
    "#research-cv": "/cv/",
    "#research-students": "/students/",
    "#research-interests": "/interests/",
    "#teaching": "/teaching/",
    "#teaching-courses": "/teaching/",
    "#teaching-resources": "/resources/",
    "#other": "/padicts/",
    "#other-padicts": "/padicts/",
    "#contact": "/contact/",
}

EXTERNAL = re.compile(r"^(https?:)?//|^(mailto|tel):")


def rewrite_href(href):
    """Map old link targets to the new URL scheme (site-root-relative)."""
    href = href.strip()
    if href in HASH_MAP:
        return HASH_MAP[href]
    # the old site has one hash link missing its '#' (a live 404)
    if "#" + href in HASH_MAP:
        return HASH_MAP["#" + href]
    if EXTERNAL.match(href):
        # protocol-less like "researchseminars.org" handled below
        return href
    if href.startswith("#"):
        print(f"  WARNING: unmapped hash link {href}")
        return href
    if href.startswith("/"):
        return href
    if "." not in href.split("/")[0] or href.split("/")[0] in ("writings", "pics", "courses", "conferences", "about"):
        # relative path into site content
        return "/" + href
    # bare domain like "researchseminars.org"
    return "https://" + href


def normalize(el):
    """Normalize a soup element in place: rewrite links, drop responsive spans."""
    for a in el.find_all("a"):
        if a.get("href"):
            a["href"] = rewrite_href(a["href"])
    # Bootstrap responsive spans: keep whichever variant is visible on desktop
    # (no hidden-md/hidden-lg), unwrap it; drop the desktop-hidden variants.
    for span in el.find_all("span"):
        cls = set(span.get("class", []))
        if not any(c.startswith("hidden-") for c in cls):
            continue
        if "hidden-md" in cls or "hidden-lg" in cls:
            span.decompose()
        else:
            span.unwrap()
    return el


def inner_html(el):
    normalize(el)
    return "".join(str(c) for c in el.contents).strip()


def clean_text(el):
    normalize(el)
    return re.sub(r"\s+", " ", el.get_text()).strip()


def cell_link(td, cls):
    """Extract href of an <a class="...cls..."> in a cell, if any."""
    a = td.find("a", class_=cls) if td else None
    href = a["href"] if a and a.get("href") else None
    return None if href == "#" else href


def dump(name, obj):
    path = DATA / name
    with open(path, "w") as f:
        yaml.dump(obj, f, allow_unicode=True, sort_keys=False, width=10000)
    n = len(obj) if isinstance(obj, list) else "-"
    print(f"wrote {path.relative_to(REPO)} ({n} entries)")


def fragment(name, html):
    path = CONTENT / name
    path.write_text(html + "\n")
    print(f"wrote {path.relative_to(REPO)}")


def arxiv_id(url):
    m = re.search(r"arxiv\.org/(?:abs|pdf)/([0-9.]+[0-9])", url or "")
    return m.group(1) if m else None


# ---------------------------------------------------------------- papers

def extract_papers(soup):
    sec = soup.find(id="research-papers")
    tables = sec.find_all("table")
    papers, theses = [], []
    for table, out in [(tables[0], papers), (tables[1], theses)]:
        for tr in table.tbody.find_all("tr"):
            tds = tr.find_all("td")
            entry = {}
            entry["title"] = clean_text(tr.find("td", class_="title"))
            with_td = tr.find("td", class_="with")
            if with_td:
                coauth = clean_text(with_td)
                if coauth:
                    entry["with"] = [w.strip() for w in coauth.split(",")]
            pdf = None
            arxiv = None
            doi = None
            for td in tds:
                pdf = pdf or cell_link(td, "pdf-download")
                arxiv = arxiv or cell_link(td, "arxiv-link")
                doi = doi or cell_link(td, "doi-link")
            if pdf:
                entry["pdf"] = rewrite_href(pdf)
            if arxiv:
                entry["arxiv"] = arxiv_id(arxiv) or arxiv
            if doi:
                entry["doi"] = doi
            notes = tr.find("td", class_="notes")
            if notes:
                nh = inner_html(notes)
                if nh:
                    entry["status"] = nh
            out.append(entry)
    dump("papers.yaml", {"articles": papers, "theses": theses})


# ---------------------------------------------------------------- talks

def extract_talks(soup):
    sec = soup.find(id="research-talks")
    talks = []
    for tr in sec.find("tbody", id="talks-body").find_all("tr"):
        tds = tr.find_all("td")
        entry = {"title": clean_text(tr.find("td", class_="title"))}
        entry["date"] = clean_text(tr.find("td", class_="dates"))
        if tr.get("data-topic"):
            entry["topic"] = tr["data-topic"]
        if tr.get("data-type"):
            entry["type"] = tr["data-type"]
        venue = tr.find("td", class_="venue")
        if venue:
            a = venue.find("a")
            entry["venue"] = clean_text(venue)
            if a and a.get("href"):
                entry["venue_url"] = rewrite_href(a["href"])
        pdf = cell_link(tr, "pdf-download")
        if pdf:
            entry["pdf"] = rewrite_href(pdf)
        # the Paper column: an arxiv or pdf link that is not the slides link
        for td in tds:
            a = td.find("a", class_="arxiv-link")
            if a:
                entry["paper"] = rewrite_href(a["href"])
                break
        # description/notes: last td if it has content and isn't one of the above
        last = tds[-1]
        if not last.find("a", class_="arxiv-link") and "venue" not in (last.get("class") or []):
            nh = inner_html(last)
            if nh:
                entry["notes"] = nh
        talks.append(entry)
    dump("talks.yaml", talks)


# ---------------------------------------------------------------- conferences

def extract_conferences(soup):
    sec = soup.find(id="research-conferences")
    confs = []
    for tr in sec.find("table").tbody.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) != 4:
            print(f"  WARNING: conference row with {len(tds)} cells: {clean_text(tr)[:60]}")
            continue
        dates, year, name_td, loc = tds
        entry = {"name": clean_text(name_td)}
        a = name_td.find("a")
        if a and a.get("href"):
            entry["url"] = rewrite_href(a["href"])
        entry["dates"] = clean_text(dates)
        entry["year"] = int(clean_text(year))
        entry["location"] = clean_text(loc)
        cls = tr.get("class") or []
        if "organizer" in cls:
            entry["role"] = "organizer"
        elif "speaker" in cls:
            entry["role"] = "speaker"
        confs.append(entry)
    # co-organizer lists live in the CV's "Conferences Organized" table, which
    # matches the organizer-role rows above 1:1 in order
    cv = soup.find(id="research-cv")
    for h2 in cv.find_all("h2"):
        if clean_text(h2) == "Conferences Organized":
            rows = h2.find_next("table").tbody.find_all("tr")
            organized = [c for c in confs if c.get("role") == "organizer"]
            if len(rows) != len(organized):
                print(f"  WARNING: {len(rows)} organized rows vs {len(organized)} organizer conferences")
            for row, conf in zip(rows, organized):
                coorg = clean_text(row.find_all("td")[1])
                conf["organizers"] = [n.strip() for n in coorg.split(",")]
    dump("conferences.yaml", confs)


# ---------------------------------------------------------------- software

# wide 302x65 banner logos (vs 65x65 circle badges), and display names for
# projects whose old markup was a bare logo image
BANNER_NAMES = {
    "lmfdb": "LMFDB",
    "psetpartners": "PSet Partners",
    "psycodict": "Psycodict",
    "researchseminars": "researchseminars.org",
    "sagemath": "SageMath",
}


def extract_software(soup):
    sec = soup.find(id="research-software")
    sections = []
    for h2 in sec.find_all("h2"):
        table = h2.find_next("table")
        projects = []
        for tr in table.tbody.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 4:
                continue
            logo_td, links_td, active_td, desc_td = tds[:4]
            entry = {}
            img = logo_td.find("img")
            label = clean_text(logo_td)
            home = logo_td.find("a")
            stem = img["src"].split("/")[-1].replace("_logo.png", "") if img else None
            entry["name"] = label or BANNER_NAMES.get(stem, stem) or "?"
            if home and home.get("href"):
                entry["url"] = rewrite_href(home["href"])
            if img:
                entry["logo"] = rewrite_href(img["src"])
                if img.get("class") and "project-logo" in img["class"]:
                    entry["banner"] = True
            links = {}
            for a in links_td.find_all("a"):
                kind = clean_text(a) or "link"
                links[kind] = rewrite_href(a["href"])
            if links:
                entry["links"] = links
            stats_a = active_td.find("a")
            if stats_a and stats_a.get("href"):
                entry["stats_url"] = rewrite_href(stats_a["href"])
            for field, cls, suffix in [("active", "active-years", ""),
                                       ("commits", "active-commits", " commits"),
                                       ("additions", "active-codeplus", " ++"),
                                       ("deletions", "active-codeminus", " --")]:
                span = active_td.find("span", class_=cls)
                if span:
                    entry[field] = clean_text(span).removesuffix(suffix)
            entry["description"] = inner_html(desc_td)
            projects.append(entry)
        sections.append({"section": clean_text(h2), "projects": projects})
    dump("software.yaml", sections)


# ---------------------------------------------------------------- courses

def extract_courses(soup):
    sec = soup.find(id="teaching-courses")
    courses = []
    for tr in sec.find("table").tbody.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 3:
            print(f"  WARNING: course row with {len(tds)} cells: {clean_text(tr)[:60]}")
            continue
        name_td, inst_td, sem_td = tds[:3]
        entry = {"name": clean_text(name_td)}
        a = name_td.find("a")
        if a and a.get("href") and "course-nolink" not in (a.get("class") or []):
            entry["url"] = rewrite_href(a["href"])
        entry["institution"] = clean_text(inst_td)
        entry["semester"] = clean_text(sem_td)
        courses.append(entry)
    dump("courses.yaml", courses)


# ---------------------------------------------------------------- cv

def extract_cv(soup):
    sec = soup.find(id="research-cv")
    cv = []
    for h2 in sec.find_all("h2"):
        title = clean_text(h2)
        link = h2.find("a")
        entry = {"section": title}
        if link:
            entry["link"] = rewrite_href(link["href"])
        if title == "Conferences Organized":
            # generated from conferences.yaml (role: organizer) at build time
            entry["generate"] = "organized"
            cv.append(entry)
            continue
        # claim the following table only if no other h2 comes first
        table = h2.find_next(["table", "h2"])
        if table and table.name == "table":
            entry["headers"] = [clean_text(th) for th in table.find_all("th")]
            rows = []
            for tr in table.tbody.find_all("tr"):
                cells = [inner_html(td) for td in tr.find_all("td")]
                rows.append(cells)
            entry["rows"] = rows
        cv.append(entry)
    dump("cv.yaml", cv)


# ---------------------------------------------------------------- profile / home

def extract_profile(soup):
    home = soup.find(id="home")
    profile = {}
    pos_links = home.select("table.position a")
    profile["name"] = "David Roe"
    profile["position"] = clean_text(pos_links[0]) if pos_links else "Principal Research Scientist"
    profile["position_url"] = pos_links[0]["href"] if pos_links else None
    profile["department"] = clean_text(pos_links[1]) if len(pos_links) > 1 else "MIT Department of Mathematics"
    profile["department_url"] = pos_links[1]["href"] if len(pos_links) > 1 else None
    profile["email"] = "roed@mit.edu"
    profile["photo"] = "/pics/david_600.jpg"
    findme = []
    for div in home.select("div.other-homes div"):
        a = div.find("a")
        if a:
            label = clean_text(a).replace("Geneology", "Genealogy")
            findme.append({"label": label, "url": rewrite_href(a["href"])})
    profile["findme"] = findme
    contact = soup.find(id="contact")
    addr = contact.find_all("p")[-1]
    profile["address"] = [clean_text(BeautifulSoup(piece, "lxml"))
                          for piece in re.split(r"<br\s*/?>", inner_html(addr)) if clean_text(BeautifulSoup(piece, "lxml"))]
    dump("profile.yaml", profile)
    blurb = home.select_one("div.home-content p")
    fragment("home_blurb.html", inner_html(blurb))


# ---------------------------------------------------------------- prose

def extract_prose(soup):
    for sec_id, name, strip_h1 in [
        ("research-interests", "interests.html", True),
        ("research-students", "students.html", True),
        ("teaching-resources", "resources.html", True),
        ("other-padicts", "padicts.html", False),
        ("contact", "contact.html", True),
    ]:
        sec = soup.find(id=sec_id)
        if strip_h1 and sec.h1:
            sec.h1.decompose()
        fragment(name, inner_html(sec))
    # intro paragraphs that live above generated tables
    talks = soup.find(id="research-talks")
    fragment("talks_intro.html", inner_html(talks.find("p")))
    confs = soup.find(id="research-conferences")
    frag = ""
    for p in confs.find_all("p"):
        frag += str(normalize(p)) + "\n"
    fragment("conferences_intro.html", frag.strip())
    courses = soup.find(id="teaching-courses")
    fragment("courses_intro.html", inner_html(courses.find("p")))


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    CONTENT.mkdir(parents=True, exist_ok=True)
    soup = BeautifulSoup(OLD.read_text(), "lxml")
    extract_papers(soup)
    extract_talks(soup)
    extract_conferences(soup)
    extract_software(soup)
    extract_courses(soup)
    extract_cv(soup)
    extract_profile(soup)
    extract_prose(soup)
    print("done")


if __name__ == "__main__":
    sys.exit(main())
