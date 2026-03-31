from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db.models import Q
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.crypto import get_random_string
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

from .forms import AdminUserCreateForm, CompanyDataForm, ReviewActionForm, VendorDocumentForm
from .excel_utils import render_document_excel
from .models import CompanyData, DocumentStatus, User, UserRole, VendorDocument, VendorProfile
from .pdf_utils import render_document_pdf


class RoleRequiredMixin(LoginRequiredMixin):
    allowed_roles = set()

    def has_allowed_role(self, user):
        if user.is_superuser:
            return True
        return not self.allowed_roles or user.role in self.allowed_roles

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not self.has_allowed_role(request.user):
            return HttpResponseForbidden("You do not have access to this area.")
        return super().dispatch(request, *args, **kwargs)


class AdminOnlyMixin(RoleRequiredMixin):
    allowed_roles = {UserRole.ADMIN}


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "vendor_portal/dashboard.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("vendor_portal:login")
        if request.user.is_superuser or request.user.role == UserRole.ADMIN:
            return redirect("vendor_portal:admin_handling")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        if user.role == UserRole.VENDOR:
            context["draft_documents"] = VendorDocument.objects.filter(
                vendor=user,
                status__in=[DocumentStatus.DRAFT, DocumentStatus.REJECTED],
            )[:5]
            context["in_review_documents"] = VendorDocument.objects.filter(
                vendor=user,
                status__in=[DocumentStatus.SUBMITTED, DocumentStatus.PURCHASE_APPROVED],
            )[:5]
            context["final_documents"] = VendorDocument.objects.filter(
                vendor=user,
                status=DocumentStatus.FINAL_APPROVED,
            )[:5]
        elif user.role == UserRole.PURCHASE:
            context["queue_documents"] = VendorDocument.objects.filter(status=DocumentStatus.SUBMITTED)[:10]
        elif user.role == UserRole.QC:
            context["queue_documents"] = VendorDocument.objects.filter(status=DocumentStatus.PURCHASE_APPROVED)[:10]
        else:
            context["queue_documents"] = VendorDocument.objects.all()[:10]

        return context


class AdminHandlingHomeView(AdminOnlyMixin, TemplateView):
    template_name = "vendor_portal/admin_handling/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["vendor_count"] = VendorProfile.objects.count()
        context["purchase_count"] = User.objects.filter(role=UserRole.PURCHASE).count()
        context["qa_count"] = User.objects.filter(role=UserRole.QC).count()
        context["company_data"] = CompanyData.objects.first()
        return context


class VendorManagementView(AdminOnlyMixin, TemplateView):
    template_name = "vendor_portal/admin_handling/vendor_management.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("form", AdminUserCreateForm(initial={"role": UserRole.VENDOR}))
        context["vendors"] = VendorProfile.objects.select_related("user")
        return context

    def post(self, request, *args, **kwargs):
        form = AdminUserCreateForm(request.POST, request.FILES)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))

        if form.cleaned_data["role"] != UserRole.VENDOR:
            form.add_error("role", "This page creates Vendor users only.")
            return self.render_to_response(self.get_context_data(form=form))

        password = get_random_string(10)
        username = form.build_username()
        role = form.cleaned_data["role"]
        user = User.objects.create_user(
            username=username,
            email=form.cleaned_data["email"],
            password=password,
            role=role,
            first_name=form.cleaned_data["full_name"],
        )
        if role == UserRole.VENDOR:
            VendorProfile.objects.create(
                user=user,
                vendor_name=form.cleaned_data["full_name"],
                phone=form.cleaned_data["phone"],
                logo=form.cleaned_data.get("logo"),
                barcode=form.cleaned_data.get("barcode"),
            )

        send_mail(
            subject=f"{user.get_role_display()} Portal Account Created",
            message=(
                f"Your portal account has been created.\n\n"
                f"Role: {user.get_role_display()}\n"
                f"Username: {username}\n"
                f"Password: {password}\n"
                f"Login URL: {request.build_absolute_uri(reverse('vendor_portal:login'))}\n"
            ),
            from_email=None,
            recipient_list=[user.email],
            fail_silently=True,
        )

        messages.success(
            request,
            f"Vendor created successfully. Login details were emailed to {user.email}.",
        )
        return redirect("vendor_portal:vendor_management")


class PurchaseManagementView(AdminOnlyMixin, TemplateView):
    template_name = "vendor_portal/admin_handling/purchase_management.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("form", AdminUserCreateForm(initial={"role": UserRole.PURCHASE}))
        context["purchase_users"] = User.objects.filter(role=UserRole.PURCHASE).order_by("first_name", "username")
        return context

    def post(self, request, *args, **kwargs):
        form = AdminUserCreateForm(request.POST, request.FILES)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))

        if form.cleaned_data["role"] != UserRole.PURCHASE:
            form.add_error("role", "This page creates Purchase users only.")
            return self.render_to_response(self.get_context_data(form=form))

        password = get_random_string(10)
        username = form.build_username()
        user = User.objects.create_user(
            username=username,
            email=form.cleaned_data["email"],
            password=password,
            role=UserRole.PURCHASE,
            first_name=form.cleaned_data["full_name"],
        )

        send_mail(
            subject="Purchase Portal Account Created",
            message=(
                f"Your portal account has been created.\n\n"
                f"Role: Purchase\n"
                f"Username: {username}\n"
                f"Password: {password}\n"
                f"Login URL: {request.build_absolute_uri(reverse('vendor_portal:login'))}\n"
            ),
            from_email=None,
            recipient_list=[user.email],
            fail_silently=True,
        )

        messages.success(request, f"Purchase user created successfully. Login details were emailed to {user.email}.")
        return redirect("vendor_portal:purchase_management")


class QaManagementView(AdminOnlyMixin, TemplateView):
    template_name = "vendor_portal/admin_handling/qa_management.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("form", AdminUserCreateForm(initial={"role": UserRole.QC}))
        context["qa_users"] = User.objects.filter(role=UserRole.QC).order_by("first_name", "username")
        return context

    def post(self, request, *args, **kwargs):
        form = AdminUserCreateForm(request.POST, request.FILES)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))

        if form.cleaned_data["role"] != UserRole.QC:
            form.add_error("role", "This page creates QA users only.")
            return self.render_to_response(self.get_context_data(form=form))

        password = get_random_string(10)
        username = form.build_username()
        user = User.objects.create_user(
            username=username,
            email=form.cleaned_data["email"],
            password=password,
            role=UserRole.QC,
            first_name=form.cleaned_data["full_name"],
        )

        send_mail(
            subject="QA Portal Account Created",
            message=(
                f"Your portal account has been created.\n\n"
                f"Role: QA\n"
                f"Username: {username}\n"
                f"Password: {password}\n"
                f"Login URL: {request.build_absolute_uri(reverse('vendor_portal:login'))}\n"
            ),
            from_email=None,
            recipient_list=[user.email],
            fail_silently=True,
        )

        messages.success(request, f"QA user created successfully. Login details were emailed to {user.email}.")
        return redirect("vendor_portal:qa_management")


class CompanyDataView(AdminOnlyMixin, TemplateView):
    template_name = "vendor_portal/admin_handling/company_data.html"

    def get_company_data(self):
        company_data = CompanyData.objects.first()
        if company_data is None:
            company_data = CompanyData.objects.create()
        return company_data

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        company_data = self.get_company_data()
        context.setdefault("form", CompanyDataForm(instance=company_data))
        context["company_data"] = company_data
        return context

    def post(self, request, *args, **kwargs):
        company_data = self.get_company_data()
        form = CompanyDataForm(request.POST, request.FILES, instance=company_data)
        if form.is_valid():
            company = form.save(commit=False)
            company.updated_by = request.user
            company.save()
            messages.success(request, "Company signature and seal data updated.")
            return redirect("vendor_portal:company_data")

        return self.render_to_response(self.get_context_data(form=form))


class VendorDocumentListView(RoleRequiredMixin, ListView):
    model = VendorDocument
    template_name = "vendor_portal/document_list.html"
    context_object_name = "documents"
    allowed_roles = {UserRole.VENDOR, UserRole.QC, UserRole.PURCHASE, UserRole.ADMIN}

    def get_queryset(self):
        user = self.request.user
        queryset = VendorDocument.objects.all().select_related("vendor")

        if user.role == UserRole.VENDOR:
            queryset = queryset.filter(vendor=user)
        elif user.role == UserRole.PURCHASE:
            queryset = queryset.filter(Q(status=DocumentStatus.SUBMITTED) | Q(status=DocumentStatus.PURCHASE_APPROVED))
        elif user.role == UserRole.QC:
            queryset = queryset.filter(Q(status=DocumentStatus.PURCHASE_APPROVED) | Q(status=DocumentStatus.FINAL_APPROVED))

        status_value = self.request.GET.get("status", "").strip()
        search_value = self.request.GET.get("q", "").strip()

        if status_value:
            queryset = queryset.filter(status=status_value)

        if search_value:
            queryset = queryset.filter(
                Q(document_number__icontains=search_value)
                | Q(customer_name__icontains=search_value)
                | Q(po_number__icontains=search_value)
                | Q(heat_number__icontains=search_value)
                | Q(vendor__first_name__icontains=search_value)
                | Q(vendor__username__icontains=search_value)
                | Q(vendor__vendor_profile__vendor_name__icontains=search_value)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["status_choices"] = DocumentStatus.choices
        context["current_status"] = self.request.GET.get("status", "").strip()
        context["current_query"] = self.request.GET.get("q", "").strip()
        return context


class VendorDocumentCreateView(RoleRequiredMixin, CreateView):
    model = VendorDocument
    form_class = VendorDocumentForm
    template_name = "vendor_portal/document_form.html"
    allowed_roles = {UserRole.VENDOR, UserRole.PURCHASE, UserRole.QC}

    def get_initial(self):
        initial = super().get_initial()
        profile = getattr(self.request.user, "vendor_profile", None)
        company_data = CompanyData.objects.first()
        if profile:
            initial.setdefault("company_name", profile.vendor_name)
        if company_data:
            initial.setdefault("company_address", company_data.company_address)
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["vendor_profile"] = getattr(self.request.user, "vendor_profile", None)
        context["company_data"] = CompanyData.objects.first()
        return context

    def form_valid(self, form):
        form.instance.vendor = self.request.user
        form.instance.status = DocumentStatus.DRAFT
        profile = getattr(self.request.user, "vendor_profile", None)
        company_data = CompanyData.objects.first()
        if profile:
            form.instance.company_name = profile.vendor_name
        if company_data:
            form.instance.company_address = company_data.company_address
        response = super().form_valid(form)
        self.object._log_action(self.request.user, "created", "Vendor created a draft document.")
        messages.success(self.request, "Draft saved successfully.")
        return response

    def get_success_url(self):
        if "submit" in self.request.POST:
            try:
                self.object.submit_for_review(self.request.user)
                messages.success(self.request, "Document submitted for Purchase review.")
            except ValidationError as exc:
                messages.error(self.request, exc.message)
        return reverse("vendor_portal:document_detail", kwargs={"pk": self.object.pk})


class VendorDocumentUpdateView(RoleRequiredMixin, UpdateView):
    model = VendorDocument
    form_class = VendorDocumentForm
    template_name = "vendor_portal/document_form.html"
    allowed_roles = {UserRole.VENDOR}

    def get_queryset(self):
        return VendorDocument.objects.filter(vendor=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        owner = self.object.vendor if getattr(self, "object", None) else self.request.user
        context["vendor_profile"] = getattr(owner, "vendor_profile", None)
        context["company_data"] = CompanyData.objects.first()
        return context

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.object.can_user_edit(request.user):
            return HttpResponseForbidden("You do not have edit permission at this workflow stage.")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        profile = getattr(self.object.vendor, "vendor_profile", None)
        company_data = CompanyData.objects.first()
        if profile:
            form.instance.company_name = profile.vendor_name
        if company_data:
            form.instance.company_address = company_data.company_address
        response = super().form_valid(form)
        actor_role = "QA" if self.request.user.role == UserRole.QC else self.request.user.get_role_display()
        self.object._log_action(self.request.user, "updated", f"{actor_role} updated the document.")
        if self.request.user.role in {UserRole.PURCHASE, UserRole.QC}:
            self.object._create_revision_snapshot(self.request.user, f"{actor_role} edited during review.")
        messages.success(self.request, "Document updated successfully.")
        return response

    def get_success_url(self):
        if "submit" in self.request.POST:
            try:
                self.object.submit_for_review(self.request.user)
                messages.success(self.request, "Document submitted for Purchase review.")
            except ValidationError as exc:
                messages.error(self.request, exc.message)
        return reverse("vendor_portal:document_detail", kwargs={"pk": self.object.pk})


class VendorDocumentAutosaveView(RoleRequiredMixin, View):
    allowed_roles = {UserRole.VENDOR}

    def post(self, request, pk):
        document = get_object_or_404(VendorDocument, pk=pk, vendor=request.user)
        if not document.is_editable:
            return JsonResponse({"ok": False, "message": "This document can no longer be edited."}, status=403)

        form = VendorDocumentForm(request.POST, instance=document)
        if form.is_valid():
            form.save()
            document._log_action(request.user, "updated", "Vendor autosaved the draft document.")
            return JsonResponse(
                {
                    "ok": True,
                    "message": "Draft autosaved.",
                    "updated_at": document.updated_at.strftime("%Y-%m-%d %H:%M"),
                }
            )

        return JsonResponse({"ok": False, "errors": form.errors}, status=400)


class VendorDocumentDetailView(RoleRequiredMixin, DetailView):
    model = VendorDocument
    template_name = "vendor_portal/document_detail.html"
    context_object_name = "document"
    allowed_roles = {UserRole.VENDOR, UserRole.QC, UserRole.PURCHASE, UserRole.ADMIN}

    def get_queryset(self):
        queryset = VendorDocument.objects.all().select_related("vendor").prefetch_related(
            "reviews__reviewer",
            "audit_logs__user",
            "revisions__created_by",
        )
        user = self.request.user
        if user.role == UserRole.VENDOR:
            return queryset.filter(vendor=user)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        document = self.object
        context["company_data"] = CompanyData.objects.first()
        context["can_edit"] = document.can_user_edit(user)
        context["can_qa_review"] = user.role == UserRole.QC and document.status == DocumentStatus.PURCHASE_APPROVED
        context["can_purchase_review"] = user.role == UserRole.PURCHASE and document.status == DocumentStatus.SUBMITTED
        context["can_download_pdf"] = document.can_generate_pdf and (
            user.role in {UserRole.QC, UserRole.PURCHASE, UserRole.ADMIN}
            or document.vendor_id == user.id
        )
        context["can_download_excel"] = context["can_download_pdf"]
        context["review_form"] = ReviewActionForm()
        return context


class VendorDocumentPdfView(RoleRequiredMixin, View):
    allowed_roles = {UserRole.VENDOR, UserRole.QC, UserRole.PURCHASE, UserRole.ADMIN}

    def get(self, request, pk):
        document = get_object_or_404(VendorDocument.objects.select_related("vendor"), pk=pk)

        if request.user.role == UserRole.VENDOR and not request.user.is_superuser and document.vendor_id != request.user.id:
            return HttpResponseForbidden("You can only download your own approved documents.")

        if not document.can_generate_pdf:
            return HttpResponseForbidden("PDF download is only available after final approval.")

        try:
            pdf_content = render_document_pdf(document)
        except RuntimeError as exc:
            messages.error(request, str(exc))
            return redirect("vendor_portal:document_detail", pk=document.pk)

        document._log_action(request.user, "pdf_downloaded", "Final approved PDF downloaded.")
        response = HttpResponse(pdf_content, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{document.document_number}.pdf"'
        return response


class VendorDocumentExcelView(RoleRequiredMixin, View):
    allowed_roles = {UserRole.VENDOR, UserRole.QC, UserRole.PURCHASE, UserRole.ADMIN}

    def get(self, request, pk):
        document = get_object_or_404(VendorDocument.objects.select_related("vendor"), pk=pk)

        if request.user.role == UserRole.VENDOR and not request.user.is_superuser and document.vendor_id != request.user.id:
            return HttpResponseForbidden("You can only download your own approved documents.")

        if not document.can_generate_pdf:
            return HttpResponseForbidden("Excel download is only available after final approval.")

        try:
            workbook_content = render_document_excel(document)
        except RuntimeError as exc:
            messages.error(request, str(exc))
            return redirect("vendor_portal:document_detail", pk=document.pk)

        document._log_action(request.user, "pdf_downloaded", "Final approved Excel certificate downloaded.")
        response = HttpResponse(workbook_content, content_type="application/vnd.ms-excel")
        response["Content-Disposition"] = f'attachment; filename="{document.document_number}.xls"'
        return response


def qa_review_view(request, pk):
    if not request.user.is_authenticated:
        return redirect(f"{reverse('vendor_portal:login')}?next={request.path}")

    if request.user.role != UserRole.QC:
        return HttpResponseForbidden("Only QA users can review Purchase-approved documents.")

    document = get_object_or_404(VendorDocument, pk=pk)
    if request.method != "POST":
        return redirect("vendor_portal:document_detail", pk=document.pk)

    form = ReviewActionForm(request.POST)
    if form.is_valid():
        try:
            document.record_qa_decision(
                request.user,
                form.cleaned_data["decision"],
                form.cleaned_data["comments"],
            )
            messages.success(request, "QA decision recorded.")
        except ValidationError as exc:
            messages.error(request, exc.message)
    else:
        messages.error(request, "Please provide a valid QA decision and comments.")

    return redirect("vendor_portal:document_detail", pk=document.pk)


class PurchaseReviewView(RoleRequiredMixin, View):
    allowed_roles = {UserRole.PURCHASE}

    def post(self, request, pk):
        document = get_object_or_404(VendorDocument, pk=pk)
        form = ReviewActionForm(request.POST)

        if form.is_valid():
            try:
                document.record_purchase_decision(
                    request.user,
                    form.cleaned_data["decision"],
                    form.cleaned_data["comments"],
                )
                messages.success(request, "Purchase decision recorded.")
            except ValidationError as exc:
                messages.error(request, exc.message)
        else:
            messages.error(request, "Please provide a valid purchase decision and comments.")

        return redirect("vendor_portal:document_detail", pk=document.pk)
