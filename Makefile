PYTHON ?= .venv/bin/python

.PHONY: dev stop check run search migrate lint
dev:
	docker compose up --build --watch

stop:
	docker compose stop

check:
	$(PYTHON) manage.py check
	$(PYTHON) manage.py makemigrations --check --dry-run

run:
	$(PYTHON) manage.py runserver

search:
	$(PYTHON) -m scripts.run_search

migrate:
	$(PYTHON) manage.py migrate

lint:
	$(PYTHON) -m ruff check apps common config safe_cli scripts manage.py
	$(PYTHON) -m ruff format --check apps common config safe_cli scripts manage.py
