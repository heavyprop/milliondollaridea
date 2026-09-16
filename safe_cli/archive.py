"""The server and downloader validate the same portable ZIP format."""

import hashlib
import mimetypes
import stat
import unicodedata
import zipfile
import zlib
from pathlib import Path

MAX_ARCHIVE = 25 * 1024 * 1024
MAX_UNPACKED = 100 * 1024 * 1024
MAX_FILES = 2000
CHUNK = 64 * 1024
RESERVED = {"CON", "PRN", "AUX", "NUL"} | {f"{prefix}{n}" for prefix in ("COM", "LPT") for n in range(1, 10)}


class ArchiveError(ValueError):
    pass


def validate_path(path):
    parts = path.split("/")
    if (
        not path or len(path.encode("utf-8")) > 768
        or path != unicodedata.normalize("NFC", path)
        or any(ord(c) < 32 or ord(c) == 127 or c in '\\:*?"<>|' for c in path)
        or any(p in ("", ".", "..") or p.endswith((".", " "))
               or len(p.encode("utf-8")) > 255
               or p.split(".")[0].upper() in RESERVED for p in parts)
    ):
        raise ArchiveError(f"Unsafe or unsupported archive path: {path!r}")
    return parts


def checksum(path):
    result = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(CHUNK), b""):
            result.update(chunk)
    return result.hexdigest()


def inspect_archive(path, *, max_archive=MAX_ARCHIVE, max_unpacked=MAX_UNPACKED, max_files=MAX_FILES):
    if Path(path).stat().st_size > max_archive:
        raise ArchiveError("Archive exceeds the upload size limit.")
    records = []
    total = 0
    names, nodes = set(), {}
    try:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            if len(entries) > max_files:
                raise ArchiveError("Archive contains too many entries.")
            for entry in entries:
                name = entry.filename[:-1] if entry.is_dir() else entry.filename
                # ZipInfo truncates names at NUL; validate the original as well.
                if entry.orig_filename != entry.filename:
                    raise ArchiveError("Archive filename contains a null byte.")
                parts = validate_path(name)
                folded = name.casefold()
                if folded in names:
                    raise ArchiveError("Archive contains duplicate or case-colliding paths.")
                names.add(folded)
                kind = "dir" if entry.is_dir() else "file"
                for length in range(1, len(parts) + 1):
                    prefix = "/".join(parts[:length])
                    expected = kind if length == len(parts) else "dir"
                    previous = nodes.get(prefix.casefold())
                    if previous is not None and previous != (prefix, expected):
                        raise ArchiveError("Archive contains conflicting file/directory paths.")
                    nodes[prefix.casefold()] = (prefix, expected)
                mode = stat.S_IFMT(entry.external_attr >> 16)
                allowed_modes = (0, stat.S_IFDIR) if entry.is_dir() else (0, stat.S_IFREG)
                if mode not in allowed_modes:
                    raise ArchiveError("Symlinks and special files are not supported.")
                if entry.flag_bits & 1 or entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                    raise ArchiveError("Encrypted or unsupported ZIP compression.")
                if entry.is_dir():
                    if entry.file_size:
                        raise ArchiveError("Directory entries cannot contain data.")
                    continue
                if entry.file_size > max_unpacked - total:
                    raise ArchiveError("Archive exceeds the unpacked size limit.")
                digest, actual, sample = hashlib.sha256(), 0, b""
                with archive.open(entry) as stream:
                    for chunk in iter(lambda: stream.read(CHUNK), b""):
                        actual += len(chunk)
                        total += len(chunk)
                        if total > max_unpacked:
                            raise ArchiveError("Archive exceeds the unpacked size limit.")
                        digest.update(chunk)
                        if len(sample) < 4096:
                            sample += chunk[:4096 - len(sample)]
                if actual != entry.file_size:
                    raise ArchiveError("Archive entry size does not match its contents.")
                try:
                    sample.decode("utf-8")
                    binary = b"\x00" in sample
                except UnicodeDecodeError:
                    binary = True
                records.append({"path": name, "size": actual, "sha256": digest.hexdigest(), "is_binary": binary, "content_type": mimetypes.guess_type(name)[0] or "application/octet-stream"})
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, EOFError, zlib.error) as exc:
        raise ArchiveError("Invalid or damaged ZIP archive.") from exc
    if not records:
        raise ArchiveError("The project must contain at least one file.")
    return records, total
