"""Repeatable sample posts for local development."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.discussions.models import Subject, Thread
from apps.discussions.services.posts import create_post

SAMPLE_POSTS = {
    "Technology": [
        ("What made Python click for you?", "Small scripts made programming feel useful to me. Renaming photos and sorting a shopping list taught me more than memorizing syntax. What was your first useful Python project?"),
        ("A weekend project with a Raspberry Pi", "I am planning a small indoor temperature dashboard. The first version would collect readings and display a daily chart. What would you build with a spare single-board computer?"),
        ("How do you organize your browser tabs?", "I keep research, documentation, and half-finished projects open until everything becomes hard to find. I am trying one bookmark folder per project. What system works for you?"),
    ],
    "Food": [
        ("Your best five-ingredient dinner", "My current favorite is pasta with tomatoes, garlic, olive oil, and basil. Keeping dinner simple makes it easier to cook after work. What would you add to a short weeknight recipe collection?"),
        ("Learning to bake bread at home", "My first loaf was dense but tasted good toasted. For the next batch I want to give the dough more time to rise and write down what changes. Which part of bread making took you longest to learn?"),
        ("Making leftovers interesting", "Yesterday's roasted vegetables became today's rice bowl with a quick lemon dressing. I like meals that can turn into something different the next day. What leftovers do you deliberately cook extra for?"),
    ],
    "Outdoors": [
        ("What makes a good local walking route?", "A quiet path, a patch of trees, and somewhere to sit are enough for me. I am trying to explore nearby streets instead of repeating the same loop. What do you look for on a short walk?"),
        ("Growing herbs on a windowsill", "I want to start with basil and mint in separate pots. There is only a small sunny space in my kitchen, so this will be an experiment. Which herbs have worked in your home?"),
        ("Keeping a nature journal", "I started noting the birds and plants I notice on walks. Sketches are rough, but recording small changes gives me a reason to look closely. Does anyone else keep a nature notebook?"),
    ],
    "Arts and Books": [
        ("A book you wanted to discuss immediately", "Some books are enjoyable alone; others make me want a reading group as soon as I finish. I especially like stories where two readers interpret the ending differently. Which book started a great conversation for you?"),
        ("Practicing drawing for ten minutes a day", "I am sketching an ordinary object each evening: a mug, a shoe, or a houseplant. The aim is to notice shapes rather than finish a polished picture. What small creative habit have you kept?"),
        ("Building a playlist for focused work", "Instrumental music helps me settle into repetitive tasks, while silence works better for reading. I am putting together a short playlist without abrupt changes. What do you listen to while creating something?"),
    ],
}


class Command(BaseCommand):
    help = "Create 12 sample posts across four subjects; reruns skip existing samples."

    def handle(self, *args, **options):
        user_model = get_user_model()
        author, created = user_model.objects.get_or_create(username="sample_content")
        if created:
            author.set_unusable_password()
            author.first_name = "Sample"
            author.last_name = "Content"
            author.save()
        elif author.has_usable_password() or author.is_staff or author.is_superuser:
            raise CommandError("Username sample_content belongs to an existing login account.")

        count = 0
        for subject_title, posts in SAMPLE_POSTS.items():
            subject, _ = Subject.objects.get_or_create(
                title=subject_title,
                defaults={"author": author, "description": f"Discussions about {subject_title.lower()}."},
            )
            for title, body in posts:
                title = f"[Sample] {title}"
                if Thread.objects.filter(author=author, title=title).exists():
                    continue
                self.stdout.write(f"Creating {title}", ending="\n")
                create_post(author=author, title=title, description=body, subject=subject)
                count += 1

        self.stdout.write(self.style.SUCCESS(f"Created {count} sample posts."))
