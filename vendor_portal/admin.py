from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import AuditLog, CompanyData, DocumentRevision, Review, User, VendorDocument, VendorProfile


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("VQMS Access", {"fields": ("role",)}),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        ("VQMS Access", {"fields": ("role",)}),
    )
    list_display = ("username", "email", "first_name", "last_name", "role", "is_staff")
    list_filter = ("role", "is_staff", "is_superuser", "is_active")


@admin.register(VendorDocument)
class VendorDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "document_number",
        "vendor",
        "customer_name",
        "status",
        "revision",
        "updated_at",
    )
    list_filter = ("status", "created_at", "updated_at")
    search_fields = ("document_number", "customer_name", "po_number", "heat_number")
    readonly_fields = ("created_at", "updated_at", "submitted_at", "qc_reviewed_at", "final_approved_at")


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("document", "reviewer", "role", "decision", "created_at")
    list_filter = ("role", "decision", "created_at")
    search_fields = ("document__document_number", "reviewer__username", "comments")
    readonly_fields = ("created_at",)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("document", "user", "action", "created_at")
    list_filter = ("action", "created_at")
    search_fields = ("document__document_number", "user__username", "notes")
    readonly_fields = ("created_at",)


@admin.register(DocumentRevision)
class DocumentRevisionAdmin(admin.ModelAdmin):
    list_display = ("document", "revision_number", "created_by", "reason", "created_at")
    list_filter = ("created_at",)
    search_fields = ("document__document_number", "created_by__username", "reason")
    readonly_fields = ("created_at",)


@admin.register(VendorProfile)
class VendorProfileAdmin(admin.ModelAdmin):
    list_display = ("vendor_name", "user", "phone", "created_at")
    search_fields = ("vendor_name", "user__username", "user__email", "phone")
    readonly_fields = ("created_at", "updated_at")


@admin.register(CompanyData)
class CompanyDataAdmin(admin.ModelAdmin):
    list_display = ("company_name", "updated_by", "updated_at")
    readonly_fields = ("updated_at",)
