PY = .venv/bin/python

build:
	$(PY) build.py

serve: build
	@echo "http://localhost:8314/"
	cd site && python3 -m http.server 8314

# refresh GitHub contribution figures in data/software.yaml (best-effort:
# on network/API trouble it keeps the old numbers and never fails the build)
stats:
	$(PY) scripts/github_stats.py

# fetch bibtex metadata for papers that don't have it yet (run after adding
# a paper to data/papers.yaml; --refresh re-fetches everything)
bib:
	$(PY) scripts/fetch_bibtex.py

deploy: stats build
	./deploy.sh

clean:
	rm -rf site

# One-time setup after cloning
venv:
	/opt/homebrew/bin/python3.13 -m venv .venv
	.venv/bin/pip install -r requirements.txt

.PHONY: build serve deploy clean venv stats bib
