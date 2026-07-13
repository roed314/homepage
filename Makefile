PY = .venv/bin/python

build:
	$(PY) build.py

serve: build
	$(PY) scripts/serve.py

# refresh GitHub contribution figures in data/software.yaml (best-effort:
# on network/API trouble it keeps the old numbers and never fails the build)
stats:
	$(PY) scripts/github_stats.py

# fetch bibtex metadata for papers that don't have it yet (run after adding
# a paper to data/papers.yaml; --refresh re-fetches everything)
bib:
	$(PY) scripts/fetch_bibtex.py

# regenerate the LaTeX CV from data/*.yaml and place the PDF where the
# website serves it (/about/cv.pdf)
TEXBIN = /Library/TeX/texbin
cv:
	$(PY) scripts/build_cv.py
	cd cv && PATH=$(TEXBIN):$$PATH latexmk -pdf -quiet -interaction=nonstopmode cv.tex cvMIT.tex publist.tex
	mkdir -p static/about
	cp cv/cv.pdf static/about/cv.pdf

deploy: stats cv build
	./deploy.sh

clean:
	rm -rf site

# One-time setup after cloning
venv:
	/opt/homebrew/bin/python3.13 -m venv .venv
	.venv/bin/pip install -r requirements.txt

.PHONY: build serve deploy clean venv stats bib cv
