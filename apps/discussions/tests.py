from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from apps.discussions.models import Subject, Thread


class SeedDemoTests(TestCase):
    @patch(
        "apps.discussions.services.posts.get_top_labels",
        return_value=[{"label": "test"}],
    )
    def test_repeat_run_preserves_posts_and_skips_classification(self, classify):
        author = get_user_model().objects.create_user(username="existing")
        existing = Thread.objects.create(
            author=author, title="Existing", description="Keep me"
        )
        call_command("seed_demo", stdout=StringIO())
        call_command("seed_demo", stdout=StringIO())
        self.assertEqual(Thread.objects.count(), 13)
        self.assertEqual(Subject.objects.count(), 4)
        self.assertEqual(classify.call_count, 12)
        self.assertFalse(
            get_user_model()
            .objects.get(username="sample_content")
            .has_usable_password()
        )
        existing.refresh_from_db()
        self.assertEqual(existing.description, "Keep me")
        sample = Thread.objects.exclude(pk=existing.pk).first()
        self.assertEqual(sample.topic_labels, [{"label": "test"}])
