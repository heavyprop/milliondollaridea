import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client, LiveServerTestCase, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from safe_cli.__main__ import SafeError, build_archive, extract_new_folder, login, normalize_server
from safe_cli.archive import ArchiveError, inspect_archive
from .models import AccessToken, Project, ProjectMembership, ProjectUpload
from .services import issue_token
from .storage import archive_path


def zip_bytes(entries):
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, value in entries:
            archive.writestr(name, value)
    return result.getvalue()


class TransferAPITests(TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.storage_override = override_settings(HOSTING_STORAGE_ROOT=Path(self.directory.name))
        self.storage_override.enable()
        self.addCleanup(self.storage_override.disable)
        self.owner = get_user_model().objects.create_user(username="owner")
        self.other = get_user_model().objects.create_user(username="other")
        self.token, self.secret = issue_token(self.owner, "CLI", can_write=True)
        self.other_token, self.other_secret = issue_token(self.other, "Other CLI", can_write=True)
        self.publish_url = reverse("hosting:api_publish", args=["owner", "sample"])
        self.download_url = reverse("hosting:api_download", args=["owner", "sample"])

    def upload(self, entries=None, secret=None, raw=None):
        content = raw if raw is not None else zip_bytes(entries or [("src/main.py", b"print('hello')\n")])
        return self.client.post(self.publish_url, {"archive": SimpleUploadedFile("project.zip", content, content_type="application/zip")}, HTTP_AUTHORIZATION="Bearer " + (secret or self.secret))

    def test_publish_download_replace(self):
        response = self.upload()
        self.assertEqual(response.status_code, 201, response.content)
        project = Project.objects.get(slug="sample")
        self.assertEqual(project.visibility, "members")
        old = project.current_upload
        self.assertEqual(old.files.get().path, "src/main.py")
        download = self.client.get(self.download_url, HTTP_AUTHORIZATION="Bearer " + self.secret)
        self.assertEqual(download.status_code, 200)
        content = b"".join(download.streaming_content)
        download.close()
        self.assertEqual(download["Cache-Control"], "private, no-store")
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            self.assertEqual(archive.read("src/main.py"), b"print('hello')\n")
        self.assertEqual(self.upload([("README.md", b"Replacement")]).status_code, 201)
        project.refresh_from_db()
        old.refresh_from_db()
        self.assertEqual(old.status, "superseded")
        self.assertNotEqual(project.current_upload_id, old.pk)
        self.assertEqual(list(project.current_upload.files.values_list("path", flat=True)), ["README.md"])

    def test_invalid_zip_preserves_existing_upload_and_cleans_storage(self):
        self.upload()
        before = Project.objects.get().current_upload_id
        for entries in [[("../outside", b"no")], [("a", b"one"), ("a/b", b"two")], [("A", b"one"), ("a", b"two")]]:
            self.assertEqual(self.upload(entries).status_code, 400)
        self.assertEqual(self.upload(raw=b"not a zip").status_code, 400)
        self.assertEqual(Project.objects.get().current_upload_id, before)
        self.assertEqual(len(list(Path(self.directory.name).iterdir())), 1)

    def test_private_projects_cannot_be_downloaded_or_replaced_by_other_users(self):
        self.upload()
        Project.objects.update(visibility="private")
        self.assertEqual(self.upload(secret=self.other_secret).status_code, 404)
        self.assertEqual(self.client.get(self.download_url, HTTP_AUTHORIZATION="Bearer " + self.other_secret).status_code, 404)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.download_url).status_code, 401)

    def test_writer_can_publish_and_readonly_token_cannot(self):
        self.upload()
        project = Project.objects.get()
        ProjectMembership.objects.create(project=project, user=self.other, role="writer")
        self.assertEqual(self.upload(secret=self.other_secret).status_code, 201)
        _, readonly = issue_token(self.owner, "Reader")
        self.assertEqual(self.upload(secret=readonly).status_code, 403)

    def test_limits_and_required_verification(self):
        self.upload()
        with override_settings(HOSTING_DOWNLOADS_PER_DAY=0):
            self.assertEqual(self.client.get(self.download_url, HTTP_AUTHORIZATION="Bearer " + self.secret).status_code, 429)
        with override_settings(HOSTING_PUBLISHES_PER_HOUR=0):
            self.assertEqual(self.upload().status_code, 429)
        with override_settings(HOSTING_MAX_UNPACKED_BYTES=2):
            self.assertEqual(self.upload().status_code, 400)
        self.assertEqual(len(list(Path(self.directory.name).iterdir())), 1)
        Project.objects.update(require_download_verification=True)
        response = self.client.get(self.download_url, HTTP_AUTHORIZATION="Bearer " + self.secret)
        self.assertEqual(response.status_code, 403)
        self.assertIn("verification", response.json()["error"])

    def test_archived_project_and_missing_storage(self):
        self.upload()
        project = Project.objects.get()
        Project.objects.update(is_archived=True)
        self.assertEqual(self.upload().status_code, 403)
        archive_path(project.current_upload.storage_key).unlink()
        self.assertEqual(self.client.get(self.download_url, HTTP_AUTHORIZATION="Bearer " + self.secret).status_code, 503)

    def test_revoked_token_and_wrong_method(self):
        self.assertEqual(self.client.get(self.publish_url, HTTP_AUTHORIZATION="Bearer " + self.secret).status_code, 405)
        AccessToken.objects.filter(pk=self.token.pk).update(revoked_at=self.token.created_at)
        self.assertEqual(self.upload().status_code, 401)

    def test_token_page_one_time_display_and_owner_only_revocation(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("hosting:cli_access"), {"name": "Laptop", "can_write": "on"})
        self.assertEqual(response.status_code, 200)
        secret = response.context["token_secret"]
        self.assertContains(response, secret)
        self.assertNotContains(self.client.get(reverse("hosting:cli_access")), secret)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(self.client.post(reverse("hosting:revoke_token", args=[self.other_token.pk])).status_code, 404)

    def test_browser_token_creation_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(reverse("hosting:cli_access"), {"name": "Blocked"}).status_code, 403)

    @override_settings(ALLOWED_HOSTS=["localhost", "testserver"])
    def test_cli_setup_has_account_and_copyable_steps(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("hosting:cli_access"), HTTP_HOST="localhost:8000")
        self.assertContains(response, "Connect your terminal.")
        self.assertContains(response, 'data-copy-target="login-command"')
        self.assertContains(response, "safe login --server http://localhost:8000")
        self.assertNotContains(response, "--allow-http")
        self.assertContains(response, "safe get owner/my-project ./downloaded-project")
        response = self.client.post(reverse("hosting:cli_access"), {"name": "MacBook", "can_write": "on"})
        self.assertContains(response, "Your token for MacBook is ready.")
        self.assertContains(response, 'data-copy-target="new-cli-token"')
        self.assertNotContains(response, '<button class="button" type="submit">Create access token</button>')

    def test_cli_setup_shows_errors_and_lan_login_flag(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("hosting:cli_access"), {"name": ""}, HTTP_HOST="testserver")
        self.assertContains(response, "This field is required.")
        self.assertContains(response, "safe login --server http://testserver --allow-http")
        self.assertIsNone(response.context["token_secret"])

    def test_help_page_explains_hosting_and_uses_code_viewer(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("hosting:help"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Files for")
        self.assertContains(response, "safe publish ./my-project")
        self.assertContains(response, "data-code-block")
        self.assertContains(response, "threads/code_blocks.js")
        self.assertContains(response, "PDFs, images, and archives")

    def test_cleanup_keeps_current_archive(self):
        self.upload()
        old = Project.objects.get().current_upload
        self.upload([("new.txt", b"new")])
        current = Project.objects.get().current_upload
        timestamp = time.time() - 48 * 3600
        for upload in [old, current]:
            os.utime(archive_path(upload.storage_key), (timestamp, timestamp))
        call_command("cleanup_hosting", dry_run=True, stdout=io.StringIO())
        self.assertTrue(archive_path(old.storage_key).exists())
        call_command("cleanup_hosting", stdout=io.StringIO())
        self.assertFalse(archive_path(old.storage_key).exists())
        self.assertTrue(archive_path(current.storage_key).exists())

    def test_members_browse_files_and_previews_use_existing_escaped_renderer(self):
        self.upload([("src/main.py", b"<script>alert('x')</script>"), ("README.md", b"Hello\n```python\nprint('hi')\n```")])
        project = Project.objects.get()
        url = reverse("hosting:project_detail", args=["owner", "sample"])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.other)
        self.assertContains(self.client.get(reverse("hosting:index")), "owner/sample")
        self.assertContains(self.client.get(url), "src/main.py")
        for file in project.current_upload.files.all():
            file_url = reverse("hosting:file_detail", args=["owner", "sample", file.pk])
            response = self.client.get(file_url)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "data-code-block")
            self.assertContains(response, "threads/code_blocks.js")
            self.assertNotContains(response, "<script>alert")
            self.assertIn("no-store", response["Cache-Control"])
        code = project.current_upload.files.get(path="src/main.py")
        self.assertContains(self.client.get(reverse("hosting:file_detail", args=["owner", "sample", code.pk])), "&lt;script&gt;")

    def test_file_browser_rejects_private_and_superseded_files(self):
        self.upload()
        project = Project.objects.get()
        old_file = project.current_upload.files.get()
        file_url = reverse("hosting:file_detail", args=["owner", "sample", old_file.pk])
        self.client.force_login(self.other)
        Project.objects.update(visibility="private")
        self.assertEqual(self.client.get(file_url).status_code, 404)
        self.assertEqual(self.client.get(reverse("hosting:project_detail", args=["owner", "sample"])).status_code, 404)
        self.upload([("replacement.txt", b"new")])
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(file_url).status_code, 404)

    def test_binary_large_and_verification_required_previews(self):
        self.upload([("binary.dat", b"\x00binary"), ("large.txt", b"a" * (256 * 1024 + 1)), ("small.txt", b"protected-content")])
        project = Project.objects.get()
        self.client.force_login(self.other)
        for name, message in [("binary.dat", "binary file"), ("large.txt", "too large to preview")]:
            file = project.current_upload.files.get(path=name)
            self.assertContains(self.client.get(reverse("hosting:file_detail", args=["owner", "sample", file.pk])), message)
        Project.objects.update(require_download_verification=True)
        file = project.current_upload.files.get(path="small.txt")
        response = self.client.get(reverse("hosting:file_detail", args=["owner", "sample", file.pk]))
        self.assertContains(response, "requires verification")
        self.assertNotContains(response, "protected-content")


class ArchiveAndCLITests(SimpleTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def test_cli_archive_excludes_secrets_and_round_trips_binary_and_executable(self):
        source = self.root / "source"
        source.mkdir()
        (source / ".env").write_text("SECRET=private")
        (source / "run.sh").write_text("#!/bin/sh\necho hello\n")
        (source / "run.sh").chmod(0o755)
        (source / "image.bin").write_bytes(bytes(range(256)))
        (source / "empty").mkdir()
        archive = self.root / "project.zip"
        self.assertEqual(build_archive(source, archive), 2)
        output = self.root / "output"
        extract_new_folder(archive, output)
        self.assertFalse((output / ".env").exists())
        self.assertEqual((output / "image.bin").read_bytes(), bytes(range(256)))
        self.assertTrue((output / "empty").is_dir())
        self.assertTrue((output / "run.sh").stat().st_mode & stat.S_IXUSR)
        with self.assertRaises(SafeError):
            extract_new_folder(archive, output)

    def test_symlink_and_zip_bomb_are_rejected(self):
        archive = self.root / "unsafe.zip"
        link = zipfile.ZipInfo("link")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        with zipfile.ZipFile(archive, "w") as zipped:
            zipped.writestr(link, "../outside")
        with self.assertRaises(ArchiveError):
            inspect_archive(archive)
        archive.write_bytes(zip_bytes([("huge.txt", b"a" * 5000)]))
        with self.assertRaises(ArchiveError):
            inspect_archive(archive, max_unpacked=100)

    def test_unsafe_paths_and_case_collisions_rejected_before_extraction(self):
        for entries in [[("/absolute", b"x")], [("../escape", b"x")], [("CON.txt", b"x")], [("src/a", b"x"), ("SRC/b", b"x")], [("folder", b"x"), ("folder/file", b"x")]]:
            archive = self.root / "unsafe.zip"
            archive.write_bytes(zip_bytes(entries))
            with self.subTest(entries=entries), self.assertRaises(ArchiveError):
                extract_new_folder(archive, self.root / "output")
            self.assertFalse((self.root / "output").exists())

    def test_server_url_policy(self):
        self.assertEqual(normalize_server("http://127.0.0.1:8000/"), "http://127.0.0.1:8000")
        self.assertEqual(normalize_server("https://example.com"), "https://example.com")
        for value in ["http://example.com", "https://user:password@example.com", "https://example.com/path"]:
            with self.assertRaises(SafeError):
                normalize_server(value)

    def test_publish_rejects_fifo_without_waiting(self):
        if not hasattr(os, "mkfifo"):
            self.skipTest("FIFO test requires POSIX")
        source = self.root / "source"
        source.mkdir()
        os.mkfifo(source / "pipe")
        with self.assertRaises(SafeError):
            build_archive(source, self.root / "project.zip")


class CLIEndToEndTests(LiveServerTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.storage_override = override_settings(HOSTING_STORAGE_ROOT=self.root / "storage")
        self.storage_override.enable()
        self.addCleanup(self.storage_override.disable)
        owner = get_user_model().objects.create_user(username="cli-owner")
        _, self.secret = issue_token(owner, "Real CLI", can_write=True)

    def test_login_publish_get_and_replace_over_http(self):
        config = self.root / "config.json"
        args = SimpleNamespace(server=self.live_server_url, allow_http=False)
        with patch("safe_cli.__main__.getpass.getpass", return_value=self.secret):
            login(args, config)
        self.assertEqual(stat.S_IMODE(config.stat().st_mode), 0o600)
        source = self.root / "sample"
        source.mkdir()
        (source / "README.md").write_text("first upload")

        def cli(*args):
            return subprocess.run([sys.executable, "-m", "safe_cli", "--config", str(config), *args], capture_output=True, text=True, timeout=20)

        result = cli("publish", str(source))
        self.assertEqual(result.returncode, 0, result.stderr)
        downloaded = self.root / "downloaded"
        result = cli("get", "cli-owner/sample", str(downloaded))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((downloaded / "README.md").read_text(), "first upload")
        (source / "README.md").write_text("second upload")
        self.assertEqual(cli("publish", str(source)).returncode, 0)
        self.assertNotEqual(cli("get", "cli-owner/sample", str(downloaded)).returncode, 0)
        another = self.root / "another"
        result = cli("get", "cli-owner/sample", str(another))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((another / "README.md").read_text(), "second upload")
