from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string

from .models import CompanyData


def pdf_link_callback(uri, rel):
    if uri.startswith(settings.MEDIA_URL):
        return str(Path(settings.MEDIA_ROOT) / uri.removeprefix(settings.MEDIA_URL))
    if uri.startswith(settings.STATIC_URL):
        static_root = getattr(settings, "STATIC_ROOT", "") or ""
        if static_root:
            return str(Path(static_root) / uri.removeprefix(settings.STATIC_URL))
    return uri


def render_document_pdf(document):
    try:
        from xhtml2pdf import pisa
    except ImportError as exc:
        raise RuntimeError(
            "xhtml2pdf is not installed. Install the packages from requirements.txt before generating PDFs."
        ) from exc

    company_data = CompanyData.objects.first()
    html = render_to_string(
        "vendor_portal/document_pdf.html",
        {
            "document": document,
            "company_data": company_data,
            "chemical_items": document.chemical_data.items(),
            "mechanical_items": document.mechanical_data.items(),
            "heat_items": document.heat_treatment_details.items(),
        },
    )

    buffer = BytesIO()
    result = pisa.CreatePDF(html, dest=buffer, link_callback=pdf_link_callback)
    if result.err:
        raise RuntimeError("PDF generation failed. Check the certificate template for invalid markup.")

    return buffer.getvalue()
