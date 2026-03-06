.PHONY: venv install lint format test migrate up down demo demo-async tree

venv:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt

install:
	.venv/bin/pip install -r requirements.txt

lint:
	PYTHONPATH=backend .venv/bin/ruff check .

format:
	.venv/bin/black .

test:
	PYTHONPATH=backend PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q

migrate:
	PYTHONPATH=backend .venv/bin/alembic -c backend/alembic.ini upgrade head

up:
	docker compose up --build

down:
	docker compose down -v

demo:
	PYTHONPATH=backend .venv/bin/python scripts/seed_account.py && PYTHONPATH=backend .venv/bin/python scripts/demo_run.py

tree:
	rg --files | sort


demo-async:
	curl -s -X POST http://localhost:8000/api/pipeline/run -H "Content-Type: application/json" -d "{\"account_name\":\"DuPont Tedlar\",\"target_segment\":\"Graphics & Signage\",\"icp_themes\":[\"protective films\",\"signage\",\"graphics\"]}"
	curl -s http://localhost:8000/api/pipeline/jobs
