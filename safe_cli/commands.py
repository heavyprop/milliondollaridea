import re
import tempfile
import urllib.parse
import uuid
from pathlib import Path

from .archive import CHUNK, MAX_ARCHIVE, checksum
from .client import read_json, request
from .errors import SafeError
from .files import build_archive, extract_new_folder


def project_parts(value):
    parts = value.split("/")
    if (
        len(parts) != 2
        or not parts[0]
        or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", parts[1])
        or len(parts[1]) > 80
    ):
        raise SafeError(
            "Use owner/project-name; project names use lowercase letters, numbers, and hyphens."
        )
    return parts


def project_url(owner, slug, operation):
    return f"/hosting/api/projects/{urllib.parse.quote(owner, safe='')}/{urllib.parse.quote(slug, safe='')}/{operation}/"


def publish(args, config):
    folder = Path(args.folder).resolve()
    identity = read_json(request(config, "/hosting/api/me/"))
    if not identity["can_publish"]:
        raise SafeError(
            "This token is download-only. Create a token with publishing enabled."
        )
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
            + archive.read_bytes()
            + f"\r\n--{boundary}--\r\n".encode()
        )
        result = read_json(
            request(
                config,
                project_url(owner, slug, "publish"),
                data=body,
                content_type=f"multipart/form-data; boundary={boundary}",
            )
        )
        print(
            f"Published {result['project']} ({result['files']} files). This is now the current project content."
        )


def get(args, config):
    owner, slug = project_parts(args.project)
    destination = Path(args.destination or slug)
    if destination.exists() or destination.is_symlink():
        raise SafeError(
            f"Destination already exists: {destination}. Choose a new folder."
        )
    with tempfile.TemporaryDirectory(prefix="safe-download-") as directory:
        archive = Path(directory) / "project.zip"
        with (
            request(config, project_url(owner, slug, "download")) as response,
            archive.open("wb") as output,
        ):
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
            raise SafeError(
                "Download checksum mismatch; no project files were extracted."
            )
        extract_new_folder(archive, destination)
    print(f"Downloaded {owner}/{slug} to {destination.resolve()}.")
