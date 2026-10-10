# SignalBridge — common commands. Run `make help` to see them.
# These are shortcuts. If `make` is not your thing, the real commands are in docs/start.md.

.PHONY: help setup-uv setup-pip demo test api agent worker seed seed-dry lint

help:
@echo "SignalBridge commands:"
@echo "  make setup-uv    - install everything with uv (recommended)"
@echo "  make setup-pip   - install everything with pip + venv"
@echo "  make demo        - run the core recovery demo (no cloud needed)"
@echo "  make test        - run unit tests"
@echo "  make api         - start the backend API (http://localhost:8000)"
@echo "  make agent       - run the ADK agent in the terminal (needs GOOGLE_API_KEY)"
@echo "  make worker      - run the background monitor once"
@echo "  make seed        - seed Firestore from fixtures/ (needs GCP auth)"
@echo "  make seed-dry    - validate fixtures -> Firestore mapping, no write"
@echo "  make lint        - check code style with ruff"

setup-uv:
uv sync --extra dev

setup-pip:
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt

demo:
python -m scripts.demo

test:
pytest -q

api:
uvicorn backend.app.main:app --reload --port 8000

agent:
adk run backend/agent

worker:
python -m backend.worker.main

seed:
python -m scripts.seed_firestore

seed-dry:
python -m scripts.seed_firestore --dry-run

lint:
ruff check .
