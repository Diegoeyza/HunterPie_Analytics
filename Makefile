# HunterPie Analytics — one-command workflows (wraps start.sh/import.sh).

VENV := .venv/bin/python
DB ?= backend/hunts.db

.PHONY: setup seed dev test lint build bench import clean

setup: ## Install backend + dashboard dependencies
	python3 -m venv .venv
	$(VENV) -m pip install -r backend/requirements.txt
	npm install --prefix dashboard

seed: ## Seed demo data (31 synthetic hunts) — HUNTS=100 to change count
	cd backend && ../$(VENV) -m app.seed --db hunts.db --hunts $${HUNTS:-31}

dev: ## Run API (:8000) + dashboard (:3000)
	./start.sh

test: ## Backend pytest + dashboard typecheck
	cd backend && ../$(VENV) -m pytest tests -q
	cd dashboard && npx tsc --noEmit

lint: ## Ruff (backend) — install with: .venv/bin/pip install ruff
	$(VENV) -m ruff check backend/app backend/tests 2>/dev/null || ruff check backend/app backend/tests

build: ## Production dashboard build
	npm run build --prefix dashboard

bench: ## 1000-hunt endpoint latency bench — HUNTS=2000 for more
	cd backend && ../$(VENV) bench.py --hunts $${HUNTS:-1000}

import: ## Import HuntExports (default dir, seeds/, or FILE=path.json)
	./import.sh $${FILE:+--file $(FILE)}

clean: ## Remove build artifacts (never the DB)
	rm -rf dashboard/.next dashboard/tsconfig.tsbuildinfo backend/.pytest_cache
	find backend -name __pycache__ -type d -prune -exec rm -rf {} +
