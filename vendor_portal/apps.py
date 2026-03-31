from django.apps import AppConfig
from django.contrib.auth import get_user_model
from django.db.models.signals import post_migrate


def create_default_superuser(sender, **kwargs):
    User = get_user_model()
    username = 'admin'
    cre = 'admin123'
    email = 'admin@example.com'

    if not User.objects.filter(username=username).exists():
        User.objects.create_superuser(username=username, email=email, password=cre)
        print(f"Created default superuser '{username}'")


class VendorPortalConfig(AppConfig):
    name = 'vendor_portal'

    def ready(self):
        post_migrate.connect(create_default_superuser, sender=self)
