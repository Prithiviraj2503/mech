from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from .forms import LoginForm
from .views import (
    AdminHandlingHomeView,
    CompanyDataView,
    DashboardView,
    PurchaseReviewView,
    PurchaseManagementView,
    QaManagementView,
    VendorManagementView,
    VendorDocumentAutosaveView,
    VendorDocumentCreateView,
    VendorDocumentDetailView,
    VendorDocumentExcelView,
    VendorDocumentListView,
    VendorDocumentPdfView,
    VendorDocumentUpdateView,
    qa_review_view,
)

app_name = "vendor_portal"

urlpatterns = [
    path("login/", LoginView.as_view(authentication_form=LoginForm, template_name="vendor_portal/login.html"), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("", DashboardView.as_view(), name="dashboard"),
    path("admin_handling/", AdminHandlingHomeView.as_view(), name="admin_handling"),
    path("admin_handling/vendors/", VendorManagementView.as_view(), name="vendor_management"),
    path("admin_handling/purchase/", PurchaseManagementView.as_view(), name="purchase_management"),
    path("admin_handling/qa/", QaManagementView.as_view(), name="qa_management"),
    path("admin_handling/company-data/", CompanyDataView.as_view(), name="company_data"),
    path("documents/", VendorDocumentListView.as_view(), name="document_list"),
    path("documents/new/", VendorDocumentCreateView.as_view(), name="document_create"),
    path("documents/<int:pk>/", VendorDocumentDetailView.as_view(), name="document_detail"),
    path("documents/<int:pk>/pdf/", VendorDocumentPdfView.as_view(), name="document_pdf"),
    path("documents/<int:pk>/excel/", VendorDocumentExcelView.as_view(), name="document_excel"),
    path("documents/<int:pk>/edit/", VendorDocumentUpdateView.as_view(), name="document_edit"),
    path("documents/<int:pk>/autosave/", VendorDocumentAutosaveView.as_view(), name="document_autosave"),
    path("documents/<int:pk>/qa-review/", qa_review_view, name="qa_review"),
    path("documents/<int:pk>/purchase-review/", PurchaseReviewView.as_view(), name="purchase_review"),
]
