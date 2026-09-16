# Running Python and Go directly (optional)

The recommended Docker workflow is in [README.md](README.md). Use this alternative if you want local Python/Go interpreters for your editor or prefer running the application outside containers. Do not run both workflows on port 8000 at the same time.

## Fresh-clone setup

Requirements: Python **3.12+**, Go **1.27.1+**, and Docker Compose (or your own PostgreSQL and Redis). Development was verified with Python 3.14.7. Go's version is declared in `apps/search/go/go.mod`.

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements/development.txt
python -m pip install -e .
cp .env.example .env
docker compose up -d --wait postgres redis
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open http://127.0.0.1:8000. Normal accounts can also register at `/accounts/`.
The example configuration uses PostgreSQL on **5433** and Redis on **6380**, bound to localhost. These ports avoid the usual local-service ports. No production data or credentials are needed.

In a second terminal:

```bash
source .venv/bin/activate
python -m scripts.run_search
```

That command loads `.env` and starts Go using the same `DATABASE_URL` as Django. The search service binds to `127.0.0.1:8080`. If it is unavailable, Django falls back to keyword search. Classification still requires the ML dependencies.

The classifier downloads its Sentence Transformers model on first use if it is not cached. To load it before serving requests:

```bash
python -m scripts.classify_text
```

For your own PostgreSQL/Redis, skip Docker and adjust `.env`. Existing installations should **keep their current `.env`, database, and private uploads** rather than copy the example over them.

## Daily use

Start Docker Desktop, then run from the project folder:

```bash
source .venv/bin/activate
docker compose up -d --wait postgres redis
python manage.py migrate
python manage.py runserver
```

In a second terminal:

```bash
source .venv/bin/activate
python -m scripts.run_search
```

For checks, use `make check` and `make lint`. Windows users should use WSL for these shell commands, or use the Docker workflow in the main README.

The Docker and host workflows use the same Compose PostgreSQL volume if run from the same checkout. Docker keeps uploads in its `hosting_data` volume; host mode uses the path in `.env` (by default `private_hosting`). Existing uploads are not copied between them automatically.
