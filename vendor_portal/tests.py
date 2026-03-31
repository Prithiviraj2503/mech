from django.core.exceptions import ValidationError
from django.test import TestCase

from .models import (
    AuditAction,
    DocumentStatus,
    ReviewDecision,
    User,
    UserRole,
    VendorDocument,
)


class WorkflowLogicTests(TestCase):
    def setUp(self):
        self.vendor = User.objects.create_user(
            username="vendor1",
            password="testpass123",
            role=UserRole.VENDOR,
        )
        self.qc = User.objects.create_user(
            username="qc1",
            password="testpass123",
            role=UserRole.QC,
        )
        self.purchase = User.objects.create_user(
            username="purchase1",
            password="testpass123",
            role=UserRole.PURCHASE,
        )
        self.other_vendor = User.objects.create_user(
            username="vendor2",
            password="testpass123",
            role=UserRole.VENDOR,
        )
        self.document = VendorDocument.objects.create(
            vendor=self.vendor,
            document_number="DOC-001",
            customer_name="ACME Steel",
        )

    def test_vendor_can_submit_draft_document(self):
        self.document.submit_for_review(self.vendor)
        self.document.refresh_from_db()

        self.assertEqual(self.document.status, DocumentStatus.SUBMITTED)
        self.assertEqual(self.document.revision, 1)
        self.assertIsNotNone(self.document.submitted_at)
        self.assertEqual(self.document.audit_logs.count(), 1)
        self.assertEqual(self.document.audit_logs.first().action, AuditAction.SUBMITTED)

    def test_other_vendor_cannot_submit_document(self):
        with self.assertRaises(ValidationError):
            self.document.submit_for_review(self.other_vendor)

    def test_qc_approval_moves_document_to_qc_approved(self):
        self.document.submit_for_review(self.vendor)
        self.document.record_qc_decision(self.qc, ReviewDecision.APPROVED, "Values match the standard.")
        self.document.refresh_from_db()

        self.assertEqual(self.document.status, DocumentStatus.QC_APPROVED)
        self.assertIsNotNone(self.document.qc_reviewed_at)
        self.assertEqual(self.document.reviews.count(), 1)
        self.assertEqual(self.document.reviews.first().role, UserRole.QC)
        self.assertEqual(self.document.audit_logs.first().action, AuditAction.QC_APPROVED)

    def test_qc_rejection_sends_document_back_for_vendor_update(self):
        self.document.submit_for_review(self.vendor)
        self.document.record_qc_decision(self.qc, ReviewDecision.REJECTED, "Hardness value is missing.")
        self.document.refresh_from_db()

        self.assertEqual(self.document.status, DocumentStatus.REJECTED)
        self.assertTrue(self.document.is_editable)
        self.assertEqual(self.document.reviews.first().decision, ReviewDecision.REJECTED)

    def test_purchase_approval_finalizes_document(self):
        self.document.submit_for_review(self.vendor)
        self.document.record_qc_decision(self.qc, ReviewDecision.APPROVED, "QC accepted.")
        self.document.record_purchase_decision(
            self.purchase,
            ReviewDecision.APPROVED,
            "Supplier and PO compliance verified.",
        )
        self.document.refresh_from_db()

        self.assertEqual(self.document.status, DocumentStatus.FINAL_APPROVED)
        self.assertIsNotNone(self.document.final_approved_at)
        self.assertTrue(self.document.can_generate_pdf)
        self.assertEqual(self.document.reviews.count(), 2)
        self.assertEqual(self.document.audit_logs.first().action, AuditAction.PURCHASE_APPROVED)

    def test_purchase_cannot_review_before_qc_approval(self):
        self.document.submit_for_review(self.vendor)

        with self.assertRaises(ValidationError):
            self.document.record_purchase_decision(
                self.purchase,
                ReviewDecision.APPROVED,
                "Trying to skip QC.",
            )

    def test_vendor_can_resubmit_after_rejection(self):
        self.document.submit_for_review(self.vendor)
        self.document.record_qc_decision(self.qc, ReviewDecision.REJECTED, "Update tensile strength.")
        self.document.submit_for_review(self.vendor)
        self.document.refresh_from_db()

        self.assertEqual(self.document.status, DocumentStatus.SUBMITTED)
        self.assertEqual(self.document.revision, 2)

    def test_final_approved_document_cannot_be_resubmitted(self):
        self.document.submit_for_review(self.vendor)
        self.document.record_qc_decision(self.qc, ReviewDecision.APPROVED, "QC accepted.")
        self.document.record_purchase_decision(
            self.purchase,
            ReviewDecision.APPROVED,
            "Purchase accepted.",
        )

        with self.assertRaises(ValidationError):
            self.document.submit_for_review(self.vendor)
