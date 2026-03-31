from django.core.management.base import BaseCommand

from vendor_portal.models import DocumentStatus, User, UserRole, VendorDocument


class Command(BaseCommand):
    help = "Create demo users and sample VQMS documents for Vendor, Purchase, and QA testing."

    def handle(self, *args, **options):
        demo_users = [
            ("vendor_demo", UserRole.VENDOR, "vendor123"),
            ("qc_demo", UserRole.QC, "qc12345"),
            ("purchase_demo", UserRole.PURCHASE, "purchase123"),
            ("admin_demo", UserRole.ADMIN, "admin12345"),
        ]

        created_users = []
        for username, role, password in demo_users:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "role": role,
                    "email": f"{username}@example.com",
                    "is_staff": role == UserRole.ADMIN,
                    "is_superuser": role == UserRole.ADMIN,
                },
            )
            if created:
                user.set_password(password)
                user.save()
                created_users.append((username, password))

        vendor = User.objects.get(username="vendor_demo")

        demo_documents = [
            ("MTC-2026-001", DocumentStatus.DRAFT, "Atlas Engineering"),
            ("MTC-2026-002", DocumentStatus.SUBMITTED, "Prime Alloys"),
            ("MTC-2026-003", DocumentStatus.PURCHASE_APPROVED, "Northern Fabrication"),
        ]

        for document_number, status, customer_name in demo_documents:
            VendorDocument.objects.get_or_create(
                document_number=document_number,
                defaults={
                    "vendor": vendor,
                    "status": status,
                    "revision": 1,
                    "customer_name": customer_name,
                    "customer_email": f"{customer_name.lower().replace(' ', '.')}@example.com",
                    "material_grade": "ASTM A106 Gr.B",
                    "material_standard": "ASTM",
                    "heat_number": f"H-{document_number[-3:]}",
                },
            )

        if created_users:
            for username, password in created_users:
                self.stdout.write(self.style.SUCCESS(f"Created user {username} / {password}"))
        else:
            self.stdout.write(self.style.WARNING("Demo users already exist."))

        self.stdout.write(self.style.SUCCESS("Demo documents are available in the portal."))
