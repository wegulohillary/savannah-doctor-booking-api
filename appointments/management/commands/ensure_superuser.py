from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create a default superuser if it does not exist"

    def handle(self, *args, **options):
        User = get_user_model()

        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser(
                username="admin",
                email="admin@example.com",
                password="StrongPassword123!",
            )
            self.stdout.write(
                self.style.SUCCESS("Superuser created: admin")
            )
        else:
            self.stdout.write("Superuser already exists")
