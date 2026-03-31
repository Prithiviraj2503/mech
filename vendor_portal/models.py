from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.db import transaction
from django.utils import timezone

from .notifications import (
    notify_purchase_on_submission,
    notify_qa_on_purchase_approval,
    notify_vendor_and_customer_on_final_approval,
    notify_vendor_on_purchase_rejection,
    notify_vendor_on_qa_rejection,
)


class UserRole(models.TextChoices):
    VENDOR = "vendor", "Vendor"
    QC = "qc", "QA"
    PURCHASE = "purchase", "Purchase"
    ADMIN = "admin", "Admin"


class User(AbstractUser):
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.VENDOR,
        help_text="Controls which stage of the VQMS workflow the user can access.",
    )

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"


class VendorProfile(models.Model):
    user = models.OneToOneField(
        "vendor_portal.User",
        on_delete=models.CASCADE,
        related_name="vendor_profile",
    )
    vendor_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=30, blank=True)
    logo = models.ImageField(upload_to="vendor_assets/logos/", blank=True, null=True)
    barcode = models.ImageField(upload_to="vendor_assets/barcodes/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["vendor_name"]

    def __str__(self):
        return self.vendor_name


class CompanyData(models.Model):
    company_name = models.CharField(max_length=255, blank=True)
    company_address = models.CharField(max_length=255, blank=True)
    signature = models.ImageField(upload_to="company_assets/signatures/", blank=True, null=True)
    seal = models.ImageField(upload_to="company_assets/seals/", blank=True, null=True)
    updated_by = models.ForeignKey(
        "vendor_portal.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="company_data_updates",
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.company_name or "Company Data"


def default_chemical_data():
    return {
        key: {"min": "", "max": "", "actual": ""}
        for key in [
            "c",
            "si",
            "mn",
            "p",
            "s",
            "cr",
            "mo",
            "ni",
            "cu",
            "v",
            "nb",
            "cr_mo",
            "cr_mo_ni_cu_v",
            "ce",
        ]
    }


def default_mechanical_data():
    return {
        "yield_strength": {"spec_min": "", "spec_max": "", "actual": ""},
        "tensile_strength": {"spec_min": "", "spec_max": "", "actual": ""},
        "elongation": {"spec_min": "", "spec_max": "", "actual": ""},
        "reduction_of_area": {"spec_min": "", "spec_max": "", "actual": ""},
        "hardness_hbv": {"spec_min": "", "spec_max": "", "actual_values": ["", "", ""]},
        "impact_test": {
            "specimen_size": "10*10*55mm",
            "test_temperature": "-46 C",
            "single_min": "",
            "average_min": "",
            "actual_values": ["", "", ""],
            "low_temp_actual": "",
        },
    }


def default_forging_data():
    return {
        "heat_no": "",
        "heat_batch_no": "",
        "forge_method": "",
        "supplier_identification": "",
    }


def default_heat_treatment_details():
    return {
        "heat_no": "",
        "heat_batch_no": "",
        "process": "",
        "furnace_type": "",
        "furnace_no": "",
        "rows": [
            {"temperature_c": "", "soaking_hours": "", "cooling_medium": ""}
            for _ in range(4)
        ],
    }


def default_line_items():
    return [
        {
            "item": "",
            "description": "",
            "specification": "",
            "production_no": "",
            "total_quantity": "",
            "supplied_quantity": "",
        }
        for _ in range(5)
    ]


class DocumentStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    SUBMITTED = "submitted", "Submitted"
    PURCHASE_APPROVED = "purchase_approved", "Purchase Approved"
    REJECTED = "rejected", "Rejected"
    FINAL_APPROVED = "final_approved", "Final Approved"


class ReviewDecision(models.TextChoices):
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class AuditAction(models.TextChoices):
    CREATED = "created", "Created"
    UPDATED = "updated", "Updated"
    SUBMITTED = "submitted", "Submitted"
    PURCHASE_APPROVED = "purchase_approved", "Purchase Approved"
    QA_APPROVED = "qa_approved", "QA Approved"
    REJECTED = "rejected", "Rejected"
    PDF_DOWNLOADED = "pdf_downloaded", "PDF Downloaded"


class VendorDocument(models.Model):
    vendor = models.ForeignKey(
        "vendor_portal.User",
        on_delete=models.CASCADE,
        related_name="documents",
    )
    document_number = models.CharField(max_length=50, unique=True)
    revision = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=DocumentStatus.choices,
        default=DocumentStatus.DRAFT,
    )
    company_name = models.CharField(max_length=255, blank=True)
    company_address = models.CharField(max_length=255, blank=True)
    barcode_value = models.CharField(max_length=100, blank=True)
    certificate_date = models.DateField(blank=True, null=True)

    customer_name = models.CharField(max_length=255)
    customer_email = models.EmailField(blank=True)
    po_number = models.CharField(max_length=100, blank=True)
    material_grade = models.CharField(max_length=100, blank=True)
    material_standard = models.CharField(max_length=100, blank=True)
    tdc_number = models.CharField(max_length=100, blank=True)

    maker = models.CharField(max_length=255, blank=True)
    mill_certificate_number = models.CharField(max_length=100, blank=True)
    raw_material_specification = models.CharField(max_length=255, blank=True)
    raw_material_standard = models.CharField(max_length=255, blank=True)
    manufacturing_process = models.CharField(max_length=255, blank=True)
    heat_number = models.CharField(max_length=100, blank=True)

    forging_data = models.JSONField(default=default_forging_data, blank=True)
    chemical_data = models.JSONField(default=default_chemical_data, blank=True)
    mechanical_data = models.JSONField(default=default_mechanical_data, blank=True)
    heat_treatment_details = models.JSONField(default=default_heat_treatment_details, blank=True)
    line_items = models.JSONField(default=default_line_items, blank=True)
    notes = models.TextField(blank=True)
    authorized_signatory = models.CharField(max_length=255, blank=True)
    signatory_role = models.CharField(max_length=255, blank=True)

    submitted_at = models.DateTimeField(blank=True, null=True)
    qc_reviewed_at = models.DateTimeField(blank=True, null=True)
    final_approved_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["vendor", "status"]),
            models.Index(fields=["document_number"]),
        ]

    def __str__(self):
        return f"{self.document_number} - {self.customer_name}"

    @property
    def is_editable(self):
        return self.status in {DocumentStatus.DRAFT, DocumentStatus.REJECTED}

    @property
    def can_generate_pdf(self):
        return self.status == DocumentStatus.FINAL_APPROVED

    def can_user_edit(self, user):
        if user.is_superuser or user.role == UserRole.ADMIN:
            return self.status != DocumentStatus.FINAL_APPROVED
        if user.role == UserRole.VENDOR:
            return user.pk == self.vendor_id and self.status in {DocumentStatus.DRAFT, DocumentStatus.REJECTED}
        if user.role == UserRole.PURCHASE:
            return self.status == DocumentStatus.SUBMITTED
        if user.role == UserRole.QC:
            return self.status == DocumentStatus.PURCHASE_APPROVED
        return False

    def snapshot_payload(self):
        return {
            "document_number": self.document_number,
            "revision": self.revision,
            "status": self.status,
            "company_name": self.company_name,
            "company_address": self.company_address,
            "barcode_value": self.barcode_value,
            "certificate_date": self.certificate_date.isoformat() if self.certificate_date else None,
            "customer_name": self.customer_name,
            "customer_email": self.customer_email,
            "po_number": self.po_number,
            "material_grade": self.material_grade,
            "material_standard": self.material_standard,
            "tdc_number": self.tdc_number,
            "maker": self.maker,
            "mill_certificate_number": self.mill_certificate_number,
            "raw_material_specification": self.raw_material_specification,
            "raw_material_standard": self.raw_material_standard,
            "manufacturing_process": self.manufacturing_process,
            "heat_number": self.heat_number,
            "forging_data": self.forging_data,
            "chemical_data": self.chemical_data,
            "mechanical_data": self.mechanical_data,
            "heat_treatment_details": self.heat_treatment_details,
            "line_items": self.line_items,
            "notes": self.notes,
            "authorized_signatory": self.authorized_signatory,
            "signatory_role": self.signatory_role,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "qc_reviewed_at": self.qc_reviewed_at.isoformat() if self.qc_reviewed_at else None,
            "final_approved_at": self.final_approved_at.isoformat() if self.final_approved_at else None,
        }

    def _log_action(self, user, action, notes=""):
        AuditLog.objects.create(document=self, user=user, action=action, notes=notes)

    def _create_revision_snapshot(self, user, reason):
        DocumentRevision.objects.create(
            document=self,
            revision_number=self.revision,
            created_by=user,
            reason=reason,
            snapshot=self.snapshot_payload(),
        )

    def _create_review(self, reviewer, role, decision, comments):
        review = Review(
            document=self,
            reviewer=reviewer,
            role=role,
            decision=decision,
            comments=comments,
        )
        review.full_clean()
        review.save()
        return review

    @transaction.atomic
    def submit_for_review(self, actor):
        if actor.role != UserRole.VENDOR:
            raise ValidationError("Only vendor users can submit documents.")

        if actor.pk != self.vendor_id:
            raise ValidationError("A vendor can only submit their own documents.")

        if self.status not in {DocumentStatus.DRAFT, DocumentStatus.REJECTED}:
            raise ValidationError("Only draft or rejected documents can be submitted.")

        self.status = DocumentStatus.SUBMITTED
        self.submitted_at = timezone.now()
        if self.revision == 0:
            self.revision = 1
        else:
            self.revision += 1
        self.full_clean()
        self.save(update_fields=["status", "submitted_at", "revision", "updated_at"])
        self._log_action(actor, AuditAction.SUBMITTED, "Document submitted for Purchase review.")
        self._create_revision_snapshot(actor, "Submitted for workflow review.")
        transaction.on_commit(lambda: notify_purchase_on_submission(self))

    @transaction.atomic
    def record_purchase_decision(self, reviewer, decision, comments):
        if reviewer.role != UserRole.PURCHASE:
            raise ValidationError("Only Purchase users can record purchase decisions.")

        if self.status != DocumentStatus.SUBMITTED:
            raise ValidationError("Purchase review is only allowed for submitted documents.")

        if not comments.strip():
            raise ValidationError("Purchase comments are required for approval or rejection.")

        self._create_review(reviewer, UserRole.PURCHASE, decision, comments)
        self.qc_reviewed_at = timezone.now()

        if decision == ReviewDecision.APPROVED:
            self.status = DocumentStatus.PURCHASE_APPROVED
            audit_action = AuditAction.PURCHASE_APPROVED
            audit_notes = comments
        else:
            self.status = DocumentStatus.REJECTED
            audit_action = AuditAction.REJECTED
            audit_notes = f"Purchase rejected document. {comments}"

        self.full_clean()
        self.save(update_fields=["status", "qc_reviewed_at", "updated_at"])
        self._log_action(reviewer, audit_action, audit_notes)
        if decision == ReviewDecision.APPROVED:
            transaction.on_commit(lambda: notify_qa_on_purchase_approval(self, comments))
        else:
            transaction.on_commit(lambda: notify_vendor_on_purchase_rejection(self, comments))

    @transaction.atomic
    def record_qa_decision(self, reviewer, decision, comments):
        if reviewer.role != UserRole.QC:
            raise ValidationError("Only QA users can record QA decisions.")

        if self.status != DocumentStatus.PURCHASE_APPROVED:
            raise ValidationError("QA review is only allowed after Purchase approval.")

        if not comments.strip():
            raise ValidationError("QA comments are required for approval or rejection.")

        self._create_review(reviewer, UserRole.QC, decision, comments)

        update_fields = ["status", "updated_at"]
        if decision == ReviewDecision.APPROVED:
            self.status = DocumentStatus.FINAL_APPROVED
            self.final_approved_at = timezone.now()
            update_fields.append("final_approved_at")
            audit_action = AuditAction.QA_APPROVED
            audit_notes = comments
        else:
            self.status = DocumentStatus.REJECTED
            audit_action = AuditAction.REJECTED
            audit_notes = f"QA rejected document. {comments}"

        self.full_clean()
        self.save(update_fields=update_fields)
        self._log_action(reviewer, audit_action, audit_notes)
        if decision == ReviewDecision.APPROVED:
            self._create_revision_snapshot(reviewer, "Final approved release snapshot.")
        if decision == ReviewDecision.APPROVED:
            transaction.on_commit(lambda: notify_vendor_and_customer_on_final_approval(self, comments))
        else:
            transaction.on_commit(lambda: notify_vendor_on_qa_rejection(self, comments))

    def clean(self):
        if self.vendor_id and self.vendor.role != UserRole.VENDOR:
            raise ValidationError({"vendor": "Only users with the vendor role can own vendor documents."})

        if self.status == DocumentStatus.FINAL_APPROVED and not self.final_approved_at:
            raise ValidationError(
                {"final_approved_at": "Final approval timestamp is required for final approved documents."}
            )

        if self.status == DocumentStatus.PURCHASE_APPROVED and not self.qc_reviewed_at:
            raise ValidationError(
                {"qc_reviewed_at": "Purchase approval timestamp is required for purchase approved documents."}
            )

        if self.pk:
            previous = VendorDocument.objects.filter(pk=self.pk).first()
            if previous and previous.status == DocumentStatus.FINAL_APPROVED:
                protected_fields = [
                    "document_number",
                    "vendor_id",
                    "customer_name",
                    "customer_email",
                    "po_number",
                    "company_name",
                    "company_address",
                    "barcode_value",
                    "certificate_date",
                    "material_grade",
                    "material_standard",
                    "tdc_number",
                    "maker",
                    "mill_certificate_number",
                    "raw_material_specification",
                    "raw_material_standard",
                    "manufacturing_process",
                    "heat_number",
                    "forging_data",
                    "chemical_data",
                    "mechanical_data",
                    "heat_treatment_details",
                    "line_items",
                    "notes",
                    "authorized_signatory",
                    "signatory_role",
                    "revision",
                ]
                changed_fields = [
                    field_name
                    for field_name in protected_fields
                    if getattr(previous, field_name) != getattr(self, field_name)
                ]
                if changed_fields:
                    raise ValidationError(
                        "Final approved documents are locked and cannot be edited."
                    )


class Review(models.Model):
    document = models.ForeignKey(
        VendorDocument,
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    reviewer = models.ForeignKey(
        "vendor_portal.User",
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    role = models.CharField(max_length=20, choices=UserRole.choices)
    decision = models.CharField(max_length=20, choices=ReviewDecision.choices)
    comments = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["role", "decision"]),
            models.Index(fields=["document", "role"]),
        ]

    def __str__(self):
        return f"{self.document.document_number} - {self.role} - {self.decision}"

    def clean(self):
        if self.role not in {UserRole.QC, UserRole.PURCHASE}:
            raise ValidationError({"role": "Only QA or Purchase reviews are valid workflow reviews."})

        if self.reviewer_id and self.reviewer.role != self.role:
            raise ValidationError({"reviewer": "Reviewer role must match the review role."})

        if self.role == UserRole.PURCHASE and self.document.status not in {
            DocumentStatus.SUBMITTED,
            DocumentStatus.PURCHASE_APPROVED,
            DocumentStatus.FINAL_APPROVED,
        }:
            raise ValidationError(
                {"document": "Purchase review is only allowed after vendor submission in the workflow."}
            )

        if self.role == UserRole.QC and self.document.status not in {
            DocumentStatus.PURCHASE_APPROVED,
            DocumentStatus.FINAL_APPROVED,
        }:
            raise ValidationError(
                {"document": "QA review is only allowed after Purchase approval in the workflow."}
            )


class AuditLog(models.Model):
    document = models.ForeignKey(
        VendorDocument,
        on_delete=models.CASCADE,
        related_name="audit_logs",
    )
    user = models.ForeignKey(
        "vendor_portal.User",
        on_delete=models.CASCADE,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=30, choices=AuditAction.choices)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["document", "created_at"]),
            models.Index(fields=["action"]),
        ]

    def __str__(self):
        return f"{self.document.document_number} - {self.action}"


class DocumentRevision(models.Model):
    document = models.ForeignKey(
        VendorDocument,
        on_delete=models.CASCADE,
        related_name="revisions",
    )
    revision_number = models.PositiveIntegerField()
    created_by = models.ForeignKey(
        "vendor_portal.User",
        on_delete=models.CASCADE,
        related_name="document_revisions",
    )
    reason = models.CharField(max_length=255)
    snapshot = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["document", "revision_number"]),
        ]

    def __str__(self):
        return f"{self.document.document_number} - R{self.revision_number}"
