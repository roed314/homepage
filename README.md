# math.mit.edu/~roed

Static site generator for David Roe's homepage.  Content lives in YAML data
files; `build.py` renders them through Jinja2 templates into `site/`.

## Layout

```
data/         one YAML file per collection — this is where content updates happen
templates/    Jinja2 page templates (templates/content/ holds prose fragments)
static/       css, js, pictures, favicon — copied verbatim into the site
build.py      the generator (~200 lines, no framework)
scripts/      extract_data.py: the one-time migration from the old index.html
site/         build output (gitignored)
```

## Common tasks

**Add a talk**: append an entry to `data/talks.yaml` (newest first), put the
slides at `writings/talks/YYYY_MM_DD.pdf` on the server (or in the deploy
tree), then build + deploy.

```yaml
- title: My talk title
  date: Jul 11, 2026
  topic: hgm          # talks with the same topic collapse under the
  type: conf          # "most recent per topic" filter; conf/sem/coll
  venue: ANTS XVII
  venue_url: https://...
  pdf: /writings/talks/2026_07_11.pdf
  paper: https://arxiv.org/abs/...   # optional
  notes: Optional description, may contain <a href="...">links</a>
```

**Add a paper**: append to `articles:` in `data/papers.yaml`, then run
`make bib` — it fetches BibTeX metadata from doi.org (via the `doi:` field,
or the arXiv DOI when only `arxiv:` is set) and stores it under `bibtex:`.
The build renders `site/bib/<key>.bib` per paper plus a combined
`site/bib/roe.bib`, linked from the papers page.
**Add a conference**: append to `data/conferences.yaml` (newest first;
`role: organizer` or `role: speaker` colors the row).  Organized conferences
take an `organizers:` list of co-organizers; the CV's "Conferences Organized"
table is generated from these entries, so there is nothing to update in
`cv.yaml`.
**Prose pages** (interests, students, resources, ...): edit the fragment in
`templates/content/`.

## Updating pages after editing data

Run `make build` (or `make serve` to preview).  Every page is regenerated
from the YAML files on each build; there is no cache to invalidate.
`make deploy` builds first, so editing YAML + deploying is enough.

## Software contribution figures

`make stats` rewrites the active-years / commits / ++ / -- numbers in
`data/software.yaml` from the GitHub contributor-stats API (login roed314).
`make deploy` runs it automatically, so the figures refresh on every deploy;
failures (offline, rate limit, not in a repo's top-100 contributors) keep the
old numbers and never block a deploy.  A `since: <year>` field on a project
pins the start of its active range where involvement predates the repo's git
history (SageMath 2006, LMFDB 2008).

Internal links in data files are site-root-relative (`/writings/...`); the
build rewrites them per page, so the site works at any mount point.

## Build & preview

```
make build      # render into site/
make serve      # build + http://localhost:8314/
```

## Deploy

```
make deploy     # build, refuse if git tree is dirty, rsync to laurent
```

See `deploy.sh` for the ssh config it expects (ProxyJump through
lovelace.mit.edu).  rsync runs without `--delete`, so server content the
build doesn't know about (writings/, courses/, conferences/*/, the old
site's stylesheets/) is never touched.

## LaTeX CV

The moderncv sources live in `cv/` (shells: `cv.tex`, `publist.tex`, plus
the not-yet-wired `cvMIT.tex` and `SoS_CV.tex`).  `make cv` runs
`scripts/build_cv.py`, which renders the data-driven sections
(Preprints/Publications, Invited Talks, Conferences Organized) from
`data/*.yaml` into `cv/generated/*.tex`; the shells `\input` those
fragments and keep everything else (preamble, References, framing)
hand-maintained.  latexmk then builds the PDFs and the CV lands at
`static/about/cv.pdf`, so the website serves the same document.
Per-entry knobs: `cv: false` (exclude from CV), `cv_section: publications`
(arXiv-only paper listed as a publication), `cv_venue:`/`title_tex:`
overrides, `cv_only: true` on software shown in the CV but not the site.
`make deploy` regenerates the CV automatically.
