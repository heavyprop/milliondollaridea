import fnmatch
import os
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path

from .archive import CHUNK, MAX_ARCHIVE, MAX_UNPACKED, inspect_archive, validate_path
from .errors import SafeError

EXCLUDED = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".DS_Store",
    "private_hosting",
}


def excluded(relative, patterns):
    if any(
        part in EXCLUDED
        or part == ".env"
        or part.startswith(".env.")
        or part.endswith(".sqlite3")
        for part in relative.parts
    ):
        return True
    name = relative.as_posix()
    return any(
        fnmatch.fnmatchcase(name, pattern)
        or fnmatch.fnmatchcase(relative.name, pattern)
        for pattern in patterns
    )


def build_archive(folder, destination):
    folder = folder.resolve()
    if not folder.is_dir():
        raise SafeError("Publish requires a project folder.")
    ignore = folder / ".safeignore"
    if ignore.is_symlink():
        raise SafeError(".safeignore must not be a symlink.")
    patterns = (
        [
            line.strip()
            for line in ignore.read_text().splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        if ignore.is_file()
        else []
    )
    count, total = 0, 0
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for current, directories, files in os.walk(folder, followlinks=False):
            current = Path(current)
            directories[:] = sorted(
                name
                for name in directories
                if not excluded((current / name).relative_to(folder), patterns)
            )
            for name in directories:
                if (current / name).is_symlink():
                    raise SafeError(
                        f"Symlinks are not supported: {(current / name).relative_to(folder)}"
                    )
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
                fd = os.open(
                    source,
                    os.O_RDONLY
                    | getattr(os, "O_NOFOLLOW", 0)
                    | getattr(os, "O_NONBLOCK", 0),
                )
                with os.fdopen(fd, "rb") as stream:
                    info = os.fstat(stream.fileno())
                    if not stat.S_ISREG(info.st_mode):
                        raise SafeError(f"Only regular files are supported: {relative}")
                    entry = zipfile.ZipInfo(relative.as_posix())
                    entry.compress_type = zipfile.ZIP_DEFLATED
                    entry.external_attr = (
                        stat.S_IFREG | (0o755 if info.st_mode & 0o111 else 0o644)
                    ) << 16
                    with archive.open(entry, "w") as target:
                        for chunk in iter(lambda: stream.read(CHUNK), b""):
                            total += len(chunk)
                            if total > MAX_UNPACKED:
                                raise SafeError(
                                    "Project exceeds the 100 MiB unpacked size limit."
                                )
                            target.write(chunk)
                count += 1
                if count > 2000 or Path(destination).stat().st_size > MAX_ARCHIVE:
                    raise SafeError(
                        "Project exceeds the 2,000 file or 25 MiB archive limit."
                    )
    records, _ = inspect_archive(destination)
    return len(records)


def extract_new_folder(archive_path, destination):
    destination = Path(os.path.abspath(destination))
    if destination.exists() or destination.is_symlink():
        raise SafeError(
            f"Destination already exists: {destination}. Choose a new folder."
        )
    if not destination.parent.is_dir():
        raise SafeError("The destination's parent directory must already exist.")
    inspect_archive(archive_path)
    with tempfile.TemporaryDirectory(
        prefix=".safe-get-", dir=destination.parent
    ) as temporary:
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
