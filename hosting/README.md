# Secure Hosting / Safe CLI

Basic account-visible folder hosting. `safe publish` uploads or replaces the complete project; `safe get` downloads the current files into a new folder. There are no commits, branches, merges, or Git wire-protocol support.

## Use it now

From the website source folder:

```bash
source .venv/bin/activate
python -m pip install --no-build-isolation --no-deps -e .
python manage.py runserver
```

The CLI is already installed in this project's virtual environment. In another terminal, activate the same environment. Alternatively, use `./safe` from the source folder without installing.

1. Sign into the website and open **Secure Hosting → Set up Safe CLI** (`/hosting/cli/`).
2. Create a token with **Allow publishing** selected. Copy the token; it appears only once.
3. Connect, entering the token at the hidden prompt:

```bash
safe login --server http://127.0.0.1:8000
safe publish ./my-project
safe get YOUR_USERNAME/my-project ./downloaded-project
```

The first publish automatically creates a project visible to signed-in accounts. Its slug defaults to a normalized folder name. Publishing to the same owner/slug replaces the entire project, including removal of files absent from the new upload. Downloading never overwrites an existing local folder.

To choose a project name, publish the current directory, or update a project shared with you as a writer:

```bash
safe publish ./folder --project custom-name
safe publish . --project custom-name
safe publish ./folder --project owner/shared-project
safe get owner/shared-project
safe logout
```

`safe logout` removes local credentials; revoke the token on the website to invalidate it on all devices. Tokens expire after 30 days. The CLI stores its token with mode 0600 in `~/.config/untrainable/safe.json`. Override the path with `SAFE_CONFIG` or the global `--config` option.

Use HTTPS outside local development. HTTP is permitted for localhost; a trusted LAN server needs the explicit `safe login --server http://LAN_IP:8000 --allow-http` option. Redirects are rejected so bearer tokens are never forwarded to redirect targets.

## What is uploaded

Regular files and empty directories inside the selected folder, packed as ZIP. Executable bits survive downloading; timestamps and other filesystem metadata are not preserved.

Default exclusions: `.git`, `.venv`, `venv`, `node_modules`, `__pycache__`, `.DS_Store`, `private_hosting`, `.env`, `.env.*`, and names ending in `.sqlite3`. These exclusions are convenience rules, not a secret scanner. Review the folder before publishing.

Optional `.safeignore` contains one shell-style pattern per line; blank lines and lines beginning with `#` are ignored. Patterns match relative paths or individual names. This is not a full `.gitignore` parser and has no negation syntax. To exclude a directory, use its name, e.g. `build`, or its relative path, e.g. `assets/generated`.

## API

All CLI endpoints require `Authorization: Bearer TOKEN`. Browser session cookies alone do not authorize transfers.

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/hosting/api/me/` | Check token and return username/read-write scope |
| POST | `/hosting/api/projects/OWNER/SLUG/publish/` | Multipart ZIP in `archive`; create/replace a project |
| GET | `/hosting/api/projects/OWNER/SLUG/download/` | Authorized ZIP stream and SHA-256 response header |

The server stores ZIPs in `HOSTING_STORAGE_ROOT` (default: `private_hosting/`), with opaque keys and no public static/media route. It validates all entries and reads all decompressed bytes before publishing. Paths, ZIP encryption, unsupported compression, symlinks, special files, conflicting names, CRC failures, file counts, and decompressed-size limits are checked. The CLI repeats validation before extracting into a new folder and verifies the archive checksum.

Uploads are stored and validated before the current database pointer changes. Account/project/token row locks serialize publication and quota accounting on PostgreSQL. Failed validation leaves existing content unchanged. Files omitted from a replacement disappear from the current project; old archives await cleanup rather than appearing as version history.

Downloads check live permissions and token state and internally issue/redeem a single-use grant. The response reserves transfer bytes before streaming; an interrupted download still uses that allowance. Protected responses use `private, no-store`.

## Defaults and limits

- 25 MiB compressed ZIP; 100 MiB actual unpacked bytes; 2,000 total ZIP entries.
- Portable UTF-8 NFC paths, at most 768 encoded bytes, with no traversal, case collisions, Windows device names, or unsafe path components.
- 100 projects per user; 20 successful publishes/hour; 100 downloads/rolling day.
- 1 GiB combined uploaded/downloaded archive bytes per account per rolling day.
- At most 10 active CLI tokens per account.

Server limits are configurable through `HOSTING_*` settings. The CLI also enforces its documented archive limits locally. The server applies account limits across tokens; add proxy request-body/network limits and storage monitoring before public deployment. Successful-transfer quotas are not an IP-based anti-abuse system.

Browser CAPTCHA integration is not included. Projects with `require_download_verification=True` reject CLI downloads with an explicit message; the flag is never silently bypassed. Basic projects default to no required verification.

## Models

`Project`, `ProjectMembership`, `ProjectUpload`, `ProjectFile`, `AccessToken`, `VerificationRequest`, `DownloadGrant`, and `TransferEvent` remain the foundation. Owners and explicit writers may publish; member-visible projects can be downloaded by any active signed-in account. Archived projects reject publishing. The hosting dashboard lists member-visible projects plus owned/shared private projects. Click a project to browse its current file paths, then click a file for a preview. Code uses the existing post code-block component; Markdown uses the existing post renderer. Previews are limited to 256 KiB and UTF-8 text. Binary files remain downloadable through the CLI. Login and project permissions apply to every preview. Projects requiring verification do not expose preview content.

## Cleanup

Current files are always retained. To remove superseded, failed, orphaned, and abandoned staging blobs older than 24 hours:

```bash
python manage.py cleanup_hosting --dry-run
python manage.py cleanup_hosting
```

Schedule cleanup periodically in deployment. Database rows are retained for diagnostics; deleting a project does not synchronously remove its blobs. Add an event-retention job before long-running public deployment. Back up the database and private storage together.

## Tests

```bash
python manage.py test hosting --settings=hosting.test_settings
```

Tests use isolated SQLite and temporary storage, without the feed's ML-model startup. The CLI end-to-end test runs a temporary localhost server and exercises login, publish, get, replacement, and overwrite refusal over HTTP. Production uses the existing PostgreSQL database. A public release still needs PostgreSQL concurrency/load tests and deployment hardening.

A basic browser file viewer is included; browser archive uploads are not yet included. Migration 0002 also makes existing published private projects visible to signed-in accounts, as requested. Owners can still use admin to mark a project private afterward; republishing preserves that choice.
