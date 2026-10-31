SHELL := /bin/bash
PY ?= python3
BACKEND := backend
FRONTEND := frontend
-include .env
export

.PHONY: setup dev backend frontend fixtures smoke clip lint

setup:
	cd $(BACKEND) && $(PY) -m pip install -q -r requirements.txt
	cd $(FRONTEND) && npm install --silent

dev:
	@trap 'kill 0' EXIT; \
	(cd $(BACKEND) && $(PY) -m uvicorn app.main:app --reload --port 8000) & \
	(cd $(FRONTEND) && npm run dev -- --port 5173) & \
	wait

backend:
	cd $(BACKEND) && $(PY) -m uvicorn app.main:app --reload --port 8000

frontend:
	cd $(FRONTEND) && npm run dev -- --port 5173

# Build fixtures/demo from DEMO_URL (needs network + keys). Without DEMO_URL, synthesizes an offline demo source.
fixtures:
	cd $(BACKEND) && $(PY) -m scripts.make_fixtures $(DEMO_URL)

smoke:
	cd $(BACKEND) && bash scripts/smoke.sh

# make clip MOMENT=m_xxxx  — approve + render from the CLI
clip:
	cd $(BACKEND) && $(PY) -m scripts.run_pipeline --approve $(MOMENT)

lint:
	cd $(BACKEND) && ruff check app scripts
	cd $(FRONTEND) && npx tsc --noEmit -p tsconfig.app.json
