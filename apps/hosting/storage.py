import os
import tempfile
import uuid
from pathlib import Path

from django.conf import settings

from safe_cli.archive import (
    MAX_ARCHIVE,
    MAX_FILES,
    MAX_UNPACKED,
    ArchiveError,
    checksum,
    inspect_archive,
)


def archive_path(key):
    # Only server-generated UUID keys may address storage.
    key = str(uuid.UUID(str(key)))
    return Path(settings.HOSTING_STORAGE_ROOT) / f"{key}.zip"


def prepare_archive(uploaded_file):
    root = Path(settings.HOSTING_STORAGE_ROOT)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    limit = getattr(settings, "HOSTING_MAX_ARCHIVE_BYTES", MAX_ARCHIVE)
    key = str(uuid.uuid4())
    final = archive_path(key)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=root, prefix="incoming-", delete=False
        ) as stream:
            temporary = Path(stream.name)
            count = 0
            for chunk in uploaded_file.chunks():
                count += len(chunk)
                if count > limit:
                    raise ArchiveError("Archive exceeds the upload size limit.")
                stream.write(chunk)
        records, unpacked = inspect_archive(
            temporary,
            max_archive=limit,
            max_unpacked=getattr(settings, "HOSTING_MAX_UNPACKED_BYTES", MAX_UNPACKED),
            max_files=getattr(settings, "HOSTING_MAX_FILES", MAX_FILES),
        )
        sha256 = checksum(temporary)
        os.replace(temporary, final)
        return key, count, unpacked, sha256, records
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
