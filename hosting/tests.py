from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import AccessToken, Project, ProjectFile, ProjectMembership, ProjectUpload, VerificationRequest, validate_project_path
from .services import authenticate_token, begin_verification, can_access, check_token_access, consume_download_grant, issue_download_grant, issue_token, publish_validated_upload


class HostingTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="owner")
        self.reader = User.objects.create_user(username="reader")
        self.stranger = User.objects.create_user(username="stranger")
        self.project = Project.objects.create(owner=self.owner, name="Example", slug="example", visibility=Project.Visibility.PRIVATE)
        self.token, self.secret = issue_token(self.owner, "Laptop", can_write=True)
        self.upload = ProjectUpload.objects.create(project=self.project, uploaded_by=self.owner, sha256="a" * 64)
        publish_validated_upload(self.upload, self.token)
        self.project.refresh_from_db()
        self.upload.refresh_from_db()

    def test_private_permissions_and_archive(self):
        self.assertTrue(can_access(self.owner, self.project, write=True))
        self.assertFalse(can_access(self.stranger, self.project))
        membership = ProjectMembership.objects.create(project=self.project, user=self.reader)
        self.assertTrue(can_access(self.reader, self.project))
        self.assertFalse(can_access(self.reader, self.project, write=True))
        membership.role = ProjectMembership.Role.WRITER
        membership.save()
        self.assertTrue(can_access(self.reader, self.project, write=True))
        self.project.is_archived = True
        self.assertFalse(can_access(self.owner, self.project, write=True))

    def test_token_digest_expiry_and_revocation(self):
        self.assertNotEqual(self.token.token_hash, self.secret)
        self.assertEqual(authenticate_token(self.secret).pk, self.token.pk)
        AccessToken.objects.filter(pk=self.token.pk).update(revoked_at=timezone.now())
        with self.assertRaises(PermissionDenied):
            authenticate_token(self.secret)
        with self.assertRaises(PermissionDenied):
            check_token_access(self.token, self.project)
        AccessToken.objects.filter(pk=self.token.pk).update(revoked_at=None, created_at=timezone.now() - timedelta(days=2), expires_at=timezone.now() - timedelta(days=1))
        with self.assertRaises(PermissionDenied):
            authenticate_token(self.secret)

    def test_readonly_token_cannot_push(self):
        token, _ = issue_token(self.owner, "Read only")
        with self.assertRaises(PermissionDenied):
            check_token_access(token, self.project, write=True)

    def test_owner_slug_unique_case_insensitively(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Project.objects.create(owner=self.owner, name="Duplicate", slug="EXAMPLE")
        Project.objects.create(owner=self.reader, name="Other owner", slug="example")

    def test_safe_file_paths_and_unique_manifest(self):
        for path in ["../secret", "/etc/passwd", "a/../b", "a//b", "./a", "a\\b", "C:/a", "a\x00b"]:
            with self.subTest(path=path), self.assertRaises(ValidationError):
                validate_project_path(path)
        validate_project_path("src/main.py")
        ProjectFile.objects.create(upload=self.upload, path="src/main.py", size=10, sha256="b" * 64)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProjectFile.objects.create(upload=self.upload, path="src/main.py", size=10, sha256="b" * 64)

    def test_grant_is_single_use_and_bound_to_token(self):
        _, secret = issue_download_grant(self.token, self.upload)
        other_token, _ = issue_token(self.owner, "Another device")
        with self.assertRaises(PermissionDenied):
            consume_download_grant(secret, other_token)
        self.assertEqual(consume_download_grant(secret, self.token).pk, self.upload.pk)
        with self.assertRaises(PermissionDenied):
            consume_download_grant(secret, self.token)

    def test_verification_required_and_single_use(self):
        self.project.require_download_verification = True
        self.project.save()
        with self.assertRaises(PermissionDenied):
            issue_download_grant(self.token, self.upload)
        verification, code = begin_verification(self.token, self.upload)
        self.assertNotEqual(verification.code_hash, code)
        with self.assertRaises(PermissionDenied):
            issue_download_grant(self.token, self.upload, verification=verification)
        # Represents a future server-validated browser challenge, not a client flag.
        verification.status = VerificationRequest.Status.APPROVED
        verification.verified_at = timezone.now()
        verification.save()
        _, secret = issue_download_grant(self.token, self.upload, verification=verification)
        with self.assertRaises(PermissionDenied):
            issue_download_grant(self.token, self.upload, verification=verification)
        self.assertEqual(consume_download_grant(secret, self.token).pk, self.upload.pk)

    def test_expired_grant_and_verification(self):
        grant, secret = issue_download_grant(self.token, self.upload)
        type(grant).objects.filter(pk=grant.pk).update(created_at=timezone.now() - timedelta(minutes=3), expires_at=timezone.now() - timedelta(minutes=1))
        with self.assertRaises(PermissionDenied):
            consume_download_grant(secret, self.token)
        verification, _ = begin_verification(self.token, self.upload)
        VerificationRequest.objects.filter(pk=verification.pk).update(status="approved", verified_at=timezone.now() - timedelta(minutes=3), created_at=timezone.now() - timedelta(minutes=3), expires_at=timezone.now() - timedelta(minutes=1))
        with self.assertRaises(PermissionDenied):
            issue_download_grant(self.token, self.upload, verification=verification)

    def test_revoking_membership_blocks_existing_grant(self):
        membership = ProjectMembership.objects.create(project=self.project, user=self.reader)
        token, _ = issue_token(self.reader, "Reader")
        _, secret = issue_download_grant(token, self.upload)
        membership.delete()
        with self.assertRaises(PermissionDenied):
            consume_download_grant(secret, token)

    def test_replacement_invalidates_old_download(self):
        _, secret = issue_download_grant(self.token, self.upload)
        replacement = ProjectUpload.objects.create(project=self.project, uploaded_by=self.owner, sha256="b" * 64)
        publish_validated_upload(replacement, self.token)
        self.upload.refresh_from_db()
        self.assertEqual(self.upload.status, ProjectUpload.Status.SUPERSEDED)
        with self.assertRaises(PermissionDenied):
            consume_download_grant(secret, self.token)

    def test_invalid_replacement_preserves_current_upload(self):
        replacement = ProjectUpload.objects.create(project=self.project, uploaded_by=self.owner)
        with self.assertRaises(ValidationError):
            publish_validated_upload(replacement, self.token)
        self.project.refresh_from_db()
        self.upload.refresh_from_db()
        self.assertEqual(self.project.current_upload_id, self.upload.pk)
        self.assertEqual(self.upload.status, ProjectUpload.Status.READY)

    def test_current_upload_cannot_reference_other_project(self):
        other = Project(owner=self.owner, name="Other", slug="other", current_upload=self.upload)
        with self.assertRaises(ValidationError):
            other.clean()

    def test_hosting_page_lists_only_owned_or_shared_projects(self):
        url = reverse("hosting:index")
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.stranger)
        self.assertNotContains(self.client.get(url), "owner/example")
        self.client.force_login(self.owner)
        response = self.client.get(url)
        self.assertContains(response, "owner/example")
        self.assertContains(response, 'href="/hosting/" aria-current="page"')
        self.assertNotContains(response, 'class="nav-search"')
