from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from hosting.models import ProjectUpload


class Command(BaseCommand):
    help = "Delete obsolete private archives older than 24 hours; keep upload metadata and current files."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        root = Path(settings.HOSTING_STORAGE_ROOT)
        cutoff = timezone.now() - timedelta(hours=24)
        count = 0
        if root.is_symlink():
            raise CommandError("Storage root must not be a symlink.")
        for path in root.glob("*"):
            if path.is_symlink() or not path.is_file() or path.stat().st_mtime >= cutoff.timestamp():
                continue
            if path.name.startswith("incoming-"):
                removable = True
            elif path.suffix == ".zip":
                upload = ProjectUpload.objects.filter(storage_key=path.stem).first()
                removable = upload is None or (
                    upload.status in (ProjectUpload.Status.FAILED, ProjectUpload.Status.SUPERSEDED)
                    and not hasattr(upload, "current_for_project")
                )
            else:
                removable = False
            if removable:
                if not options["dry_run"]:
                    path.unlink(missing_ok=True)
                count += 1
        self.stdout.write(f"{'Would remove' if options['dry_run'] else 'Removed'} {count} obsolete archives/staging files.")
