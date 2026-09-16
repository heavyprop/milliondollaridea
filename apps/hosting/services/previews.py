"""Bounded, permission-aware archive previews for the project browser."""

import zipfile
from pathlib import PurePosixPath

from apps.hosting.storage import archive_path
from common.content import split_post_content


def file_preview(project, upload, file):
    context = {}
    limit = 256 * 1024
    if project.require_download_verification:
        context["preview_message"] = (
            "This project requires verification. File previews will be available when browser verification is enabled."
        )
    elif file.size > limit:
        context["preview_message"] = (
            "This file is too large to preview (256 KiB limit). Download the project with Safe CLI to view it."
        )
    elif file.is_binary:
        context["preview_message"] = (
            "This is a binary file. Download the project with Safe CLI to open it."
        )
    else:
        try:
            with zipfile.ZipFile(archive_path(upload.storage_key)) as archive:
                with archive.open(file.path) as stream:
                    data = stream.read(limit + 1)
            if len(data) > limit:
                context["preview_message"] = (
                    "This file is too large to preview. Download the project with Safe CLI to view it."
                )
            elif b"\x00" in data:
                context["preview_message"] = (
                    "This is a binary file. Download the project with Safe CLI to open it."
                )
            else:
                content = data.decode("utf-8-sig")
                extension = PurePosixPath(file.path).suffix.lower()
                if extension in (".md", ".markdown"):
                    context["blocks"] = split_post_content(content)
                else:
                    languages = {
                        ".py": "Python",
                        ".js": "JavaScript",
                        ".ts": "TypeScript",
                        ".tsx": "TSX",
                        ".jsx": "JSX",
                        ".html": "HTML",
                        ".css": "CSS",
                        ".json": "JSON",
                        ".sh": "Shell",
                        ".sql": "SQL",
                        ".java": "Java",
                        ".rs": "Rust",
                        ".c": "C",
                        ".cpp": "C++",
                    }
                    context["blocks"] = [
                        {
                            "kind": "code",
                            "language": languages.get(extension, "Text"),
                            "text": content,
                        }
                    ]
                if not content:
                    context["preview_message"] = "This file is empty."
        except UnicodeDecodeError:
            context["preview_message"] = (
                "This file isn't UTF-8 text. Download the project with Safe CLI to open it."
            )
        except (OSError, KeyError, zipfile.BadZipFile, RuntimeError):
            context["preview_message"] = "The stored file is currently unavailable."
            return context, 503
    return context, 200
