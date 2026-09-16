# Architecture

## Feature ownership

| App | Owns | Main modules |
| --- | --- | --- |
| `apps.accounts` | Authentication/profile | `views.py`, `urls.py`, templates |
| `apps.discussions` | Discussion data and interactions | `models/`, `selectors.py`, `services/`, `views/` |
| `apps.feed` | Homepage composition | `views.py`, `selectors.py` |
| `apps.search` | Search workflow and integration | `views.py`, `services.py`, `selectors.py`, `client.py`, `fallback.py` |
| `apps.recommendations` | ML topic labels and interest profiles | `classification.py`, `interests.py` |
| `apps.hosting` | Project files, access, transfers | `models.py`, `services/`, `api/`, `views/`, `storage.py` |

A Django app need not have database models. Feed/search/recommendations are coherent features, not new tables. Small apps keep simple modules; larger ones use packages with specific names.

## Request flow

```text
config/urls.py -> feature urls.py -> view
                                  -> selector (database reads)
                                  -> service (workflow/writes)
                                       -> client (external protocol)
                                  -> template or HTTP response
```

Discussion creation calls `apps.discussions.services.posts.create_post`, which classifies through recommendations and saves the post. Detail pages query comments through discussion selectors and record engagement through services. Feed selectors reuse discussion query helpers.

Search calls `apps.search.services.search_threads`: classify the query, call Go, then hydrate ranked IDs. Only an unavailable Go service triggers Python fallback tokenization and keyword selection. SQL/scoring runs in Go; Django owns authentication and presentation. Python tokenization and keyword selection run only when Go is unavailable; there is no Python ranking implementation.

Interest profiles still use the latest 200 interaction records with event decay and retain 100 topics. They are not yet used to rank the homepage. Changing app boundaries did not change the recommendation formula.

## Database identity and existing installations

Discussion data formerly lived in `home`, while discussion views lived in `threads`. Both now belong to **`apps.discussions`**. Its `DiscussionsConfig` keeps `label = "home"` as a persistence compatibility identifier, and presents **Discussions** in Django admin.

This deliberately preserves:

- Existing `home_*` SQL tables and primary/foreign keys.
- Historical migration records and relationships inside migrations.
- Content types, permissions such as `home.change_thread`, and existing assignments.
- Go's queries against those tables.

There is no runtime `home` or `threads` Python package. Use `apps.discussions.models` for imports and `makemigrations home` for discussion migrations. Do not rename the database label or rewrite applied migrations just to match a directory name.

Accounts and hosting retain their existing labels. Hosting's historical validator import now points to `apps.hosting.models`; its callable behaviour and migration operations are unchanged. New databases apply the same history, while existing databases retain their identities. `makemigrations --check` should report no changes after this refactor.

## Cross-feature dependencies

- Feed and search query discussion models/selectors.
- Discussion creation and search use recommendation classification.
- Interest profiles read discussion interactions.
- Hosting does not import discussion views/template tags; it uses `common.content` and shared components.
- `common/` does not import feature modules.
- `safe_cli/` has no Django dependency. Hosting reuses its archive validation code.

No model is loaded by importing the classifier module. Classification loads/caches the model on first use per process. The vocabulary lives in `data/taxonomy/` and is resolved relative to the source location.

## Configuration

`config/settings/base.py` holds shared app wiring. `development.py` uses PostgreSQL/Redis and debug mode. `production.py` requires deployment credentials and enables HTTPS protections.

`config/environment.py` reads simple `.env` entries without shell execution or variable interpolation. Existing environment variables win. Quote values containing spaces; double-quoted values use JSON escaping. Set `DJANGO_ENV_FILE` to an alternate file when needed. The example file contains only development defaults.

The standalone CLI package remains separate in `pyproject.toml`; the web app runs from the checkout. Dependencies live in `requirements/web.txt`, `ml.txt`, and `development.txt`.

`requirements/development.txt` includes the formatter/linter. The unused historical SQLite snapshot is kept locally in `.local/legacy.sqlite3`, outside versioned source; active PostgreSQL and private uploads retain their previous locations.

## Go service

```text
apps/search/go/
  cmd/search/main.go              Process startup
  internal/search/server.go       HTTP contract
  internal/search/database.go     Pool and candidate loading
  internal/search/queries/candidates.sql
  internal/search/scoring.go      Ranking
  internal/search/text.go         Tokenization
  internal/search/models.go       Data structures
```

The SQL is embedded at build time. The service binds to localhost by default. Compose sets `SEARCH_LISTEN_ADDR=0.0.0.0:8080` for internal container traffic without publishing a host port; Django is the authenticated entry point. `scripts/run_search.py` shares `.env` database configuration with Django. SQL and ranking formulas are unchanged by the reorganization.

## Hosting and CLI

Hosting views own browser pages. API modules own bearer-token HTTP handling. Services separate project access, token lifecycle, quotas, upload publication, download grants, file previews, and transfer transactions. `storage.py` handles private archive storage. Authorization still precedes upload parsing, and write/grant operations retain their transactions and locks.

The CLI separates `cli.py` (dispatch), `client.py` (transport), `config.py` (credentials), `commands.py` (workflows), `files.py` (packing/extraction), `archive.py` (validation), and `errors.py`. Both `safe` and `python -m safe_cli` are supported.

## Presentation

Shared base/navigation/errors/content rendering live in `templates/`. Shared styles and code-block scripts live in `static/site/`. Feature templates and assets are namespaced inside each app. All public URLs and URL names are retained.


## Previous paths

| Old location | Current location |
| --- | --- |
| `home/models.py` or `home/models/` | `apps/discussions/models/` |
| `home/migrations/` | `apps/discussions/migrations/` |
| `threads/views.py` or `threads/views/` | `apps/discussions/views/` |
| `threads/user_interests.py` | `apps/recommendations/interests.py` |
| `threads/label_classifier.py` / `ml/topic_classifier.py` | `apps/recommendations/classification.py` |
| `home/views.py` | `apps/feed/views.py`, `apps/search/views.py`, `apps/accounts/views.py` |
| `home/go_search.py` | `apps/search/client.py` |
| `home/scoring.py` | Removed; live ranking is in `apps/search/go/internal/search/scoring.go` |
| `accounts/`, `hosting/` | `apps/accounts/`, `apps/hosting/` |
| `untrainable/` | `config/` |
| `Go/` | `apps/search/go/` |
| `model/tags/` | `data/taxonomy/` |
| `model/model_template.py` | `scripts/classify_text.py` |
| `documentation/`, root `security.md` | `docs/` |
