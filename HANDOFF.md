# Handoff: rebuild of math.mit.edu/~roed/

Context document for a session taking over this project.  Written 2026-07-13.

## What this is

A ground-up rebuild of David Roe's academic homepage as a YAML-data-driven
static site.  The old site is a single hand-edited 2,028-line `index.html`
(hash-based SPA on Bootstrap 3/jQuery, deployed at https://math.mit.edu/~roed/).
The new site generates 12 real pages from YAML via Jinja2, dependency-free CSS,
same visual identity (navy `#152737` / gold `#c4b257` / cream `#faf8f0`,
Playfair Display small-caps).

**Nothing has been committed or deployed yet.** The working tree in this repo
(`~/claude/homepage`, remote `github.com:roed314/homepage.git`, branch `main`,
one stub commit) contains the entire new site, unstaged.  The user has not yet
asked for a commit.  The live site is still the old one.

## Locations

- `~/claude/homepage` — this repo, the new site.  Everything happens here.
- `~/claude/current_homepage` — copy of the OLD site's working directory.
  Its `index.html` is NEWER than what is deployed (contains ~May 2025 edits
  that were never uploaded: extra paper, 2025 conferences, Students section,
  a landing-page prototype).  All data was extracted from this local copy,
  not the deployed site.  Also contains content not in the new repo:
  `courses/` (186 MB), `writings/` (34 MB of paper/talk PDFs), `conferences/`
  (hosted conference mini-sites, incl. recent `Lat26`, `lean-lmfdb2`),
  `wedding/`, `rec/`, `ww.tar.gz` — personal stuff that must never be
  deleted from the server.
- `~/Documents/Math/Website/...` — the user's original copies.  macOS TCC
  **blocks this session's access to ~/Documents entirely**; that's why the
  user copied things into `~/claude/`.

## Build system

- `make build` → `.venv/bin/python build.py` renders `data/*.yaml` +
  `templates/` into `site/` (gitignored).  Full regeneration each time,
  no cache.  `make serve` = build + http.server on **port 8314**.
- venv: `.venv` (homebrew python3.13; `make venv` recreates; deps in
  `requirements.txt`: jinja2, pyyaml + bs4/lxml only for the old extractor).
- All internal links in data/templates are site-root-relative (`/writings/x`);
  the `|u` filter (single urls) and `|rel` filter (embedded HTML strings)
  relativize per page depth at render time, so the site works at any mount
  point (localhost root now, `/~roed/` on the server).  Templates use
  `{{ '/papers/'|u }}`, `{{ html|rel|safe }}`.
- Nav structure (sections/subpages) is the `SECTIONS`/`PAGES` tables at the
  top of `build.py`.
- Preview from Claude Code: `.claude/launch.json` **in ~/claude/lmfdb**
  (the session's primary working dir, not this repo) has a "homepage" config
  serving `~/claude/homepage/site` on 8314.  Browser-pane gotcha: taking a
  screenshot right after scrolling sometimes captures a broken composite
  (header at bottom, blank page); workaround is resize the viewport tall
  (e.g. 1280x1500) and screenshot without scrolling.

## Data files (source of truth)

- `papers.yaml` — `articles:` + `theses:`, newest first.  Each paper may have
  `pdf` (site-relative), `arxiv` (bare id, old-style `math/0601508` ok),
  `doi` (full url), `status` (HTML allowed), `with` (coauthor list, order as
  displayed, excludes Roe), and `bibtex: {type, key, fields:{...}}` fetched
  by `scripts/fetch_bibtex.py`.
- `talks.yaml` — 78 entries; `topic` + `type` (conf/sem/coll) drive the
  client-side filters in `static/js/site.js` (untyped talks count as both —
  deliberate fix of an old-site bug that hid them).
- `conferences.yaml` — 102 entries; `role: organizer|speaker` colors rows
  gold/blue; organizer entries carry `organizers:` (co-organizer list).
  The CV's "Conferences Organized" table is GENERATED from these (the
  cv.yaml entry is just `{section, link, generate: organized}`) — don't
  reintroduce duplication.
- `cv.yaml` — generic sections: `headers` + `rows` of HTML cells, or `link`
  (cross-link h2), or the `generate` marker above.
- `software.yaml` — 3 sections of projects; `banner: true` = wide 302x65 logo,
  else circle logo + name pill; stats fields `active/commits/additions/
  deletions` are refreshed by `scripts/github_stats.py`; optional
  `since: <year>` pins the start of `active` where involvement predates git
  history (SageMath 2006, LMFDB 2008).
- `courses.yaml`, `profile.yaml` (findme links, photo, address).
- Prose lives in `templates/content/*.html` fragments (interests, students,
  resources, padicts, contact, home_blurb, three table intros).

**`scripts/extract_data.py` is the one-time migration** from
`~/claude/current_homepage/index.html`.  It was kept consistent with all
data decisions made during migration, BUT the YAML files have since been
edited by other scripts and by hand (bibtex blocks, refreshed stats, `since:`
fields, typo fixes like Feburary→February).  **Re-running it would lose those
— don't run it again**; it's kept for reference only.

## Scripts / Makefile targets

- `make bib` → `scripts/fetch_bibtex.py`: for papers without `bibtex:`,
  fetches BibTeX via doi.org content negotiation (`Accept:
  application/x-bibtex`), using `doi:` or else the arXiv DOI
  `10.48550/arXiv.<id>`; parses fields into papers.yaml.  `--refresh`
  refetches all.  DataCite (arXiv) entries come back with URL-shaped keys —
  key normalization to `Surname_Year` was done post-hoc; if you refetch new
  papers, check the keys are sane.  Theses have no DOI → no bibtex (fine).
- `make stats` → `scripts/github_stats.py`: GitHub contributor-stats API,
  login `roed314`, token from `$GITHUB_TOKEN` or `gh auth token` (anonymous
  works).  Handles 202-retry; repos where roed314 isn't in the top-100
  contributors (or network failure) keep old numbers with a warning, exit 0.
  Attribution is by login, so commits under other emails are missed (PSet
  Partners/CMFs ranges shrank slightly; user was told, use `since:` to fix).
  Last run 2026-07-13 (LMFDB 3,332 commits etc.).
- `make deploy` → runs `stats`, `build`, then `deploy.sh`.

## build.py output extras

- `site/bib/<key>.bib` per paper + combined `site/bib/roe.bib` (rendered from
  the stored fields; skips copyright/keywords/issn/isbn; adds
  `eprint`/`archiveprefix` from the paper's `arxiv`).  Papers page has a gray
  BibTeX badge per row + combined button in the h1.
- The home page (`templates/home.html`) carries an inline script redirecting
  old hash bookmarks (`#research-talks` → `talks/`).  The blurb paragraph is
  COMMENTED OUT with a Jinja comment (user request) — text preserved in
  `templates/content/home_blurb.html`.  "Find me on" pills are at the BOTTOM
  of the page (user request).  The p-adic watermark (`pics/padicbg.png`) is a
  body background at full opacity — the image is inherently faint; do NOT put
  opacity on it (it disappears; that bug already happened once).  Hidden on
  ≤850px.
- Landing layout: the user chose "Variant A" (full-width hero + 6 tiles);
  the framed Variant B was deleted.

## Deployment (NOT yet done)

`deploy.sh`: rsync `site/` → laurent.mit.edu via ProxyJump through
lovelace.mit.edu (laurent needs 2FA from outside MIT, lovelace doesn't).
Blockers before first deploy:
1. `REMOTE_DIR=www` is a **placeholder** — user must confirm the real web
   root on laurent and set up the `Host laurent` ssh config block (documented
   in deploy.sh).
2. Deliberately NO `--delete`: server-only content (writings/, courses/,
   conferences/*/,  wedding/, old stylesheets/js) must survive.  The new
   css/js live at new paths (`css/site.css`, `js/site.js`) so nothing
   collides with the old site's files.
3. First deploy replaces the old SPA `index.html` — that's the cutover.

## Open items

1. **Initial git commit** — tree is entirely unstaged; user hasn't asked yet.
   Suggested before further work.
2. **Content updates** (user's original item 3): talks/papers/conferences
   since ~May 2025 are missing (e.g. whatever Lat26 / lean-lmfdb2 in
   `~/claude/current_homepage/conferences/` are about); interests/blurb
   text updates.  User will drive.
3. **New photos**: user says they exist, but only the 2015
   `david1_small.jpg` was found (resized to `static/pics/david_600.jpg`,
   94 KB).  Ask where they are.
4. **Old `#research-PRS` page** (MIT Principal Research Scientist application
   materials, hidden subpage of the old site, still live) was NOT migrated —
   user hasn't decided keep/drop.  Also: Apache directory listings are on
   (`/pics/`, `/writings/` browsable) — flagged, no decision.
5. **Data fix suggested to user**: Ahmadi–Shparlinski status line says
   "Experimental Mathematics 23 (2023)" but Crossref says volume 32 — likely
   transposition typo in `papers.yaml` status.
6. **TODO in README**: generate the CV PDF (`about/cv.pdf` is currently a
   separately-maintained file) from the same data.
7. Possible nicety discussed: one-line tagline under the name on the home
   hero (middle ground between nothing and the commented-out blurb).

## History quirks worth knowing

- The old site's markup had bugs faithfully repaired during extraction:
  unclosed `</a>`/`</tr>`, `<tr class="speaker"x>`, `href="research-conferences"`
  (missing `#`, a live 404 on the old CV), `doi/arxiv: '#'` placeholders on
  theses, "Feburary"/"Febuary" typos, "Math Geneology" → Genealogy.
- CV Employment/Teaching institution cells used TWO different Bootstrap
  responsive-span patterns; the extractor's `normalize()` handles both
  (keep desktop-visible variant).
- Sage Days 87 dates differ between old conferences table ("July 17-21") and
  old CV ("July 17-22"); conferences.yaml value won.  CMS 2015 entry named
  "CMS Winter Meeting…" (conferences) vs "CMS Winter Session…" (old CV);
  conferences.yaml name won.
