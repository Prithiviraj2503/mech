from django.core.management.base import BaseCommand

from vendor_portal.models import User, UserRole


class Command(BaseCommand):
    help = "Ensure an initial admin user exists."

    def handle(self, *args, **options):
        admin_username = "admin"
        admin_email = "admin@example.com"
        admin_password = "admin123"  # Change this in production!

        user, created = User.objects.get_or_create(
            username=admin_username,
            defaults={
                "email": admin_email,
                "role": UserRole.ADMIN,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if created:
            user.set_password(admin_password)
            user.save()
            self.stdout.write(
                self.style.SUCCESS(f"Created initial admin user: {admin_username} with password: {admin_password}")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Initial admin user {admin_username} already exists.")
            )