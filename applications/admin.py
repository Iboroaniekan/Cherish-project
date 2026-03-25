from django.utils.html import format_html
from django.contrib import admin
from .models import Application
# Register your models here.
@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("reference_id", "proposed_name_1", "user", "status", "updated_at","passport_preview",
        "signature_preview","nin_preview","colored_status","account_type")
    list_filter = ("status", "created_at","user__profile__account_type")
    search_fields = ("reference_id", "proposed_name_1", "user__email", "user__username")
    list_editable = ("status",)
    readonly_fields = ("reference_id", "created_at", "updated_at","user", "proposed_name_1", "proposed_name_2",
        "nature_of_business", "business_type", "state", "lga", "business_address",
        "owner_first_name", "owner_last_name", "owner_email", "owner_phone",
        "business_description", "passport", "signature", "nin","status")

    fieldsets = (
        ("Reference & Status", {"fields": ( "status", "agent_note")}),
        ("Business", {"fields": ("proposed_name_1", "proposed_name_2", "nature_of_business", "business_type", "business_description")}),
        ("Address", {"fields": ("state", "lga", "business_address")}),
        ("Owner", {"fields": ("owner_first_name", "owner_last_name", "owner_email", "owner_phone")}),
        ("Uploads", {"fields": ("passport", "signature", "nin")}),
        ("Meta", {"fields": ("user",)}),
    )
    def account_type(self, obj):
        if hasattr(obj.user, "profile"):
            return obj.user.profile.account_type
        return "N/A"
    # Staff cannot add new applications
    def has_add_permission(self, request):
        return request.user.is_superuser  # only superuser can add

    # Staff cannot delete applications
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser  # only superuser can delete

    # Staff can only edit agent_note
    def get_readonly_fields(self, request, obj=None):
        if not request.user.is_superuser:
            # everything except agent_note is read-only
            return self.readonly_fields
        return []  # superuser can edit all

    actions = ["mark_approved", "mark_queried"]

    def mark_approved(self, request, queryset):
        queryset.update(status=Application.Status.APPROVED)
    mark_approved.short_description = "Mark selected applications as Approved"

    def mark_queried(self, request, queryset):
        queryset.update(status=Application.Status.QUERIED)
    mark_queried.short_description = "Mark selected applications as Queried"
    
     # Preview uploaded files
    def passport_preview(self, obj):
        if obj.passport:
            return format_html('<img src="{}" width="50"/>', obj.passport.url)
        return "-"
    passport_preview.short_description = "Passport"

    def signature_preview(self, obj):
        if obj.signature:
            return format_html('<img src="{}" width="50"/>', obj.signature.url)
        return "-"
    signature_preview.short_description = "Signature"

    def nin_preview(self, obj):
        if obj.nin:
            if obj.nin.url.lower().endswith(".pdf"):
                return format_html('<a href="{}" target="_blank">PDF</a>', obj.nin.url)
            else:
                return format_html('<img src="{}" width="50"/>', obj.nin.url)
        return "-"
    nin_preview.short_description = "NIN"
 # Colored status in list
    def colored_status(self, obj):
        color = {
            'submitted': 'gray',
            'pending': 'blue',
            'queried': 'orange',
            'approved': 'green'
        }.get(obj.status, 'black')
        return format_html('<span style="color:{};">{}</span>', color, obj.get_status_display())
    colored_status.short_description = "Status"