import argparse
import fnmatch
import getpass
import ipaddress
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from pathlib import Path

from .archive import ArchiveError, CHUNK, MAX_ARCHIVE, MAX_UNPACKED, checksum, inspect_archive, validate_path

EXCLUDED = {".git", ".venv", "venv", "node_modules", "__pycache__", ".DS_Store", "private_hosting"}


class SafeError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward bearer tokens to a redirect target.
        return None


def normalize_server(value, allow_http=False):
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
        raise SafeError("Use a server origin such as https://example.com (no path or credentials).")
    local = parsed.hostname == "localhost"
    try:
        local = local or ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:
        pass
    if parsed.scheme == "http" and not local and not allow_http:
        raise SafeError("Use HTTPS, or --allow-http for a trusted development network.")
    return value.rstrip("/")


def request(config, path, *, data=None, content_type=None):
    headers = {"Authorization": f"Bearer {config['token']}", "User-Agent": "UnTrainable-Safe/0.1"}
    if content_type:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(config["server"] + path, data=data, headers=headers)
    try:
        return urllib.request.build_opener(NoRedirect()).open(req, timeout=120)
    except urllib.error.HTTPError as exc:
        try:
            message = json.loads(exc.read(8192)).get("error", f"HTTP {exc.code}")
        except (ValueError, AttributeError):
            message = f"Server returned HTTP {exc.code}. Check the server address and token."
        raise SafeError(message) from None
    except urllib.error.URLError as exc:
        raise SafeError(f"Cannot reach the server: {exc.reason}") from None


def read_json(response):
    with response:
        try:
            return json.loads(response.read(65536))
        except ValueError:
            raise SafeError("Server returned an invalid response.") from None


def load_config(path):
    try:
        data = json.loads(path.read_text())
        data["server"] = normalize_server(data["server"], data.get("allow_http", False))
        if not isinstance(data["token"], str) or not data["token"]:
            raise ValueError()
        return data
    except FileNotFoundError:
        raise SafeError("Run safe login first.") from None
    except (ValueError, KeyError, TypeError):
        raise SafeError("Invalid Safe configuration. Run safe login again.") from None


def login(args, config_path):
    server = normalize_server(args.server, args.allow_http)
    token = getpass.getpass("CLI token (from Secure Hosting → Set up Safe CLI): ").strip()
    if not token:
        raise SafeError("A token is required.")
    config = {"server": server, "token": token, "allow_http": args.allow_http}
    identity = read_json(request(config, "/hosting/api/me/"))
    config_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=config_path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            os.chmod(temporary, 0o600)
            json.dump(config, stream)
        os.replace(temporary, config_path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
    print(f"Connected to {server} as {identity['username']}.")


def excluded(relative, patterns):
    if any(part in EXCLUDED or part == ".env" or part.startswith(".env.") or part.endswith(".sqlite3") for part in relative.parts):
        return True
    name = relative.as_posix()
    return any(fnmatch.fnmatchcase(name, pattern) or fnmatch.fnmatchcase(relative.name, pattern) for pattern in patterns)


def build_archive(folder, destination):
    folder = folder.resolve()
    if not folder.is_dir():
        raise SafeError("Publish requires a project folder.")
    ignore = folder / ".safeignore"
    if ignore.is_symlink():
        raise SafeError(".safeignore must not be a symlink.")
    patterns = [line.strip() for line in ignore.read_text().splitlines() if line.strip() and not line.lstrip().startswith("#")] if ignore.is_file() else []
    count, total = 0, 0
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for current, directories, files in os.walk(folder, followlinks=False):
            current = Path(current)
            directories[:] = sorted(name for name in directories if not excluded((current / name).relative_to(folder), patterns))
            for name in directories:
                if (current / name).is_symlink():
                    raise SafeError(f"Symlinks are not supported: {(current / name).relative_to(folder)}")
            if current != folder and not directories and not files:
                relative = current.relative_to(folder).as_posix()
                validate_path(relative)
                archive.writestr(relative + "/", b"")
            for name in sorted(files):
                source = current / name
                relative = source.relative_to(folder)
                if excluded(relative, patterns):
                    continue
                validate_path(relative.as_posix())
                if source.is_symlink():
                    raise SafeError(f"Symlinks are not supported: {relative}")
                if not stat.S_ISREG(source.lstat().st_mode):
                    raise SafeError(f"Only regular files are supported: {relative}")
                fd = os.open(source, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
                with os.fdopen(fd, "rb") as stream:
                    info = os.fstat(stream.fileno())
                    if not stat.S_ISREG(info.st_mode):
                        raise SafeError(f"Only regular files are supported: {relative}")
                    entry = zipfile.ZipInfo(relative.as_posix())
                    entry.compress_type = zipfile.ZIP_DEFLATED
                    entry.external_attr = (stat.S_IFREG | (0o755 if info.st_mode & 0o111 else 0o644)) << 16
                    with archive.open(entry, "w") as target:
                        for chunk in iter(lambda: stream.read(CHUNK), b""):
                            total += len(chunk)
                            if total > MAX_UNPACKED:
                                raise SafeError("Project exceeds the 100 MiB unpacked size limit.")
                            target.write(chunk)
                count += 1
                if count > 2000 or Path(destination).stat().st_size > MAX_ARCHIVE:
                    raise SafeError("Project exceeds the 2,000 file or 25 MiB archive limit.")
    records, _ = inspect_archive(destination)
    return len(records)


def project_parts(value):
    parts = value.split("/")
    if len(parts) != 2 or not parts[0] or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", parts[1]) or len(parts[1]) > 80:
        raise SafeError("Use owner/project-name; project names use lowercase letters, numbers, and hyphens.")
    return parts


def project_url(owner, slug, operation):
    return f"/hosting/api/projects/{urllib.parse.quote(owner, safe='')}/{urllib.parse.quote(slug, safe='')}/{operation}/"


def publish(args, config):
    folder = Path(args.folder).resolve()
    identity = read_json(request(config, "/hosting/api/me/"))
    if not identity["can_publish"]:
        raise SafeError("This token is download-only. Create a token with publishing enabled.")
    project = args.project or re.sub(r"[^a-z0-9]+", "-", folder.name.lower()).strip("-")
    if "/" not in project:
        project = f"{identity['username']}/{project}"
    owner, slug = project_parts(project)
    with tempfile.TemporaryDirectory(prefix="safe-publish-") as directory:
        archive = Path(directory) / "project.zip"
        count = build_archive(folder, archive)
        print(f"Publishing {count} files to {owner}/{slug}…")
        boundary = "safe-" + uuid.uuid4().hex
        body = (
            f'--{boundary}\r\nContent-Disposition: form-data; name="archive"; filename="project.zip"\r\nContent-Type: application/zip\r\n\r\n'.encode()
            + archive.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
        )
        result = read_json(request(config, project_url(owner, slug, "publish"), data=body, content_type=f"multipart/form-data; boundary={boundary}"))
        print(f"Published {result['project']} ({result['files']} files). This is now the current project content.")


def extract_new_folder(archive_path, destination):
    destination = Path(os.path.abspath(destination))
    if destination.exists() or destination.is_symlink():
        raise SafeError(f"Destination already exists: {destination}. Choose a new folder.")
    if not destination.parent.is_dir():
        raise SafeError("The destination's parent directory must already exist.")
    inspect_archive(archive_path)
    with tempfile.TemporaryDirectory(prefix=".safe-get-", dir=destination.parent) as temporary:
        stage = Path(temporary) / "project"
        stage.mkdir()
        with zipfile.ZipFile(archive_path) as archive:
            for entry in archive.infolist():
                target = stage.joinpath(*entry.filename.rstrip("/").split("/"))
                if entry.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(entry) as source, target.open("xb") as output:
                    shutil.copyfileobj(source, output, CHUNK)
                target.chmod(0o755 if (entry.external_attr >> 16) & 0o111 else 0o644)
        # Reserve the destination without clobbering an existing directory.
        destination.mkdir()
        try:
            for child in stage.iterdir():
                child.rename(destination / child.name)
        except Exception:
            # Only this newly created directory is owned by this operation.
            shutil.rmtree(destination)
            raise


def get(args, config):
    owner, slug = project_parts(args.project)
    destination = Path(args.destination or slug)
    if destination.exists() or destination.is_symlink():
        raise SafeError(f"Destination already exists: {destination}. Choose a new folder.")
    with tempfile.TemporaryDirectory(prefix="safe-download-") as directory:
        archive = Path(directory) / "project.zip"
        with request(config, project_url(owner, slug, "download")) as response, archive.open("wb") as output:
            expected = response.headers.get("X-Archive-SHA256", "")
            if not re.fullmatch(r"[a-f0-9]{64}", expected):
                raise SafeError("Server did not provide a valid archive checksum.")
            count = 0
            for chunk in iter(lambda: response.read(CHUNK), b""):
                count += len(chunk)
                if count > MAX_ARCHIVE:
                    raise SafeError("Download exceeds the archive size limit.")
                output.write(chunk)
        if checksum(archive) != expected:
            raise SafeError("Download checksum mismatch; no project files were extracted.")
        extract_new_folder(archive, destination)
    print(f"Downloaded {owner}/{slug} to {destination.resolve()}.")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="safe", description="Publish and download project folders with Secure Hosting.")
    parser.add_argument("--config", type=Path, default=Path(os.environ.get("SAFE_CONFIG", Path.home() / ".config/untrainable/safe.json")), help="Path to local credentials")
    commands = parser.add_subparsers(dest="command", required=True)
    login_parser = commands.add_parser("login", help="Save a CLI access token")
    login_parser.add_argument("--server", default="http://127.0.0.1:8000")
    login_parser.add_argument("--allow-http", action="store_true", help="Allow HTTP on a trusted development network")
    publish_parser = commands.add_parser("publish", help="Upload or replace a whole project folder")
    publish_parser.add_argument("folder", nargs="?", default=".")
    publish_parser.add_argument("--project", help="Project slug or owner/slug (defaults to folder name)")
    get_parser = commands.add_parser("get", help="Download into a new folder")
    get_parser.add_argument("project", help="owner/project-name")
    get_parser.add_argument("destination", nargs="?")
    commands.add_parser("logout", help="Remove the saved token from this computer")
    args = parser.parse_args(argv)
    try:
        if args.command == "login":
            login(args, args.config)
        elif args.command == "logout":
            args.config.unlink(missing_ok=True)
            print("Local credentials removed. Revoke the token on the website if it is no longer needed.")
        elif args.command == "publish":
            publish(args, load_config(args.config))
        else:
            get(args, load_config(args.config))
    except (SafeError, ArchiveError, OSError, ValueError) as exc:
        parser.exit(1, f"safe: {exc}\n")
    except KeyboardInterrupt:
        parser.exit(130, "\nsafe: cancelled\n")


if __name__ == "__main__":
    main()
