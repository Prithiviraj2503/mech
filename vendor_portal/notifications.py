from django.apps import apps
from django.conf import settings
from django.core.mail import send_mail


def _send_notification(subject, message, recipients):
    recipient_list = sorted({email for email in recipients if email})
    if not recipient_list:
        return

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            recipient_list=recipient_list,
            fail_silently=False,
        )
    except Exception as e:
        print(f"Error sending notification email: {str(e)}")


def _role_emails(role):
    User = apps.get_model("vendor_portal", "User")
    return User.objects.filter(role=role).exclude(email="").values_list("email", flat=True)


def notify_purchase_on_submission(document):
    subject = f"New document submitted for Purchase review: {document.document_number}"
    message = (
        f"Vendor {document.vendor.username} has submitted document {document.document_number}.\n\n"
        f"Customer: {document.customer_name}\n"
        f"PO Number: {document.po_number or '-'}\n"
        f"Material Grade: {document.material_grade or '-'}\n"
        f"Current Status: {document.get_status_display()}\n"
    )
    _send_notification(subject, message, _role_emails("purchase"))


def notify_qa_on_purchase_approval(document, comments):
    subject = f"Purchase approved document for QA review: {document.document_number}"
    message = (
        f"Purchase has approved document {document.document_number} and it is ready for QA review.\n\n"
        f"Vendor: {document.vendor.username}\n"
        f"Customer: {document.customer_name}\n"
        f"Purchase Comments: {comments}\n"
        f"Current Status: {document.get_status_display()}\n"
    )
    _send_notification(subject, message, _role_emails("qc"))


def notify_vendor_on_purchase_rejection(document, comments):
    subject = f"Document rejected by Purchase: {document.document_number}"
    message = (
        f"Purchase rejected document {document.document_number}.\n\n"
        f"Customer: {document.customer_name}\n"
        f"Comments: {comments}\n"
        f"Please update the document and resubmit it.\n"
    )
    _send_notification(subject, message, [document.vendor.email])


def notify_vendor_and_customer_on_final_approval(document, comments):
    subject = f"Document fully approved by QA: {document.document_number}"
    message = (
        f"Document {document.document_number} has received final QA approval.\n\n"
        f"Vendor: {document.vendor.username}\n"
        f"Customer: {document.customer_name}\n"
        f"QA Comments: {comments}\n"
        f"Current Status: {document.get_status_display()}\n"
        f"The document is now eligible for final PDF generation and customer release.\n"
    )
    _send_notification(subject, message, [document.vendor.email, document.customer_email])


def notify_vendor_on_qa_rejection(document, comments):
    subject = f"Document rejected by QA: {document.document_number}"
    message = (
        f"QA rejected document {document.document_number}.\n\n"
        f"Customer: {document.customer_name}\n"
        f"Comments: {comments}\n"
        f"Please review the QA comments, update the document, and resubmit it.\n"
    )
    _send_notification(subject, message, [document.vendor.email])
