from django.utils.html import format_html
from django.contrib import admin,messages
from .models import Application,NameReservation, Payment, SystemFee
from django.utils.safestring import mark_safe
from django import forms
from django.utils import timezone


class ApplicationAdminForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            # Keep agent_note input always empty
            self.fields['agent_note'].initial = ""
            self.fields['agent_note'].widget.attrs.update({
                "placeholder": "Type new query here...",
                "style": "resize: none;"  # fixed size, no manual resize
            })

@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    form = ApplicationAdminForm
    list_display = ("reference_id", "proposed_name_1", "user", "colored_status", "updated_at",
                    "passport_preview", "signature_preview", "nin_preview", "account_type","registration_number_display","qr_code_preview")
    list_filter = ("status", "created_at", "user__profile__account_type")
    search_fields = ("reference_id", "proposed_name_1", "user__email", "user__username","registration_number")
    # list_editable = ("status",)
    
    readonly_fields = (
        "reference_id", "created_at", "updated_at", "user",
        "proposed_name_1", "proposed_name_2", "nature_of_business", "business_type",
        "state", "lga", "business_address", "owner_first_name", "owner_last_name",
        "owner_email", "owner_phone", "business_description",
        "passport", "signature", "nin",
        "status", "highlighted_query_note", "previous_query_notes","qr_code_preview","registration_number_display"
    )

    fieldsets = (
        ("User Query", {"fields": ("highlighted_query_note", "previous_query_notes", "agent_note")}),
        ("Reference & Status", {"fields": ("status","qr_code_preview","registration_number_display")}),
        ("Business", {"fields": ("proposed_name_1", "proposed_name_2", "nature_of_business", "business_type", "business_description")}),
        ("Address", {"fields": ("state", "lga", "business_address")}),
        ("Owner", {"fields": ("owner_first_name", "owner_last_name", "owner_email", "owner_phone")}),
        ("Uploads", {"fields": ("passport", "signature", "nin")}),
        ("Meta", {"fields": ("user",)}),
    )

    def highlighted_query_note(self, obj):
        return format_html('<div>{}</div>', obj.agent_note) if obj.agent_note else "-"
    highlighted_query_note.short_description = "Active Query"

    def previous_query_notes(self, obj):
        if obj.previous_notes:
            html = "".join(f'<div style="margin-bottom:5px;">{note}</div>' for note in reversed(obj.previous_notes))
            return mark_safe(html)
        return "-"
    previous_query_notes.short_description = "Previous Queries"

    def registration_number_display(self, obj):
        return obj.registration_number or "-"
    registration_number_display.short_description = "RC Number"

     # Override save_model to move old note to previous_notes if new note is typed
    def save_model(self, request, obj, form, change):
        if change:
            old_obj = Application.objects.get(pk=obj.pk)

            # If status manually changed to APPROVED
            if obj.status == Application.Status.APPROVED and old_obj.status != Application.Status.APPROVED:
                # Generate registration_number, token, and QR if missing
                if not obj.registration_number:
                    obj.registration_number = obj.generate_registration_number()
                if not obj.verification_token:
                    obj.verification_token = obj.generate_verification_token()
                obj.generate_qr_code()
                obj.approved_at = timezone.now()
                obj.approved_by = request.user
                obj.generate_signature()
                obj.generate_and_save_certificate()

            # Handle query notes as before
            new_note = form.cleaned_data.get("agent_note", "").strip()
            if new_note:
                if obj.agent_note:
                    obj.previous_notes.append(obj.agent_note)
                obj.agent_note = new_note
                obj.status = Application.Status.QUERIED

        super().save_model(request, obj, form, change)
#  ACCOUNT TYPE
    def account_type(self, obj):
        if hasattr(obj.user, "profile"):
            return obj.user.profile.account_type
        return "N/A"

# Permissions
    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def get_readonly_fields(self, request, obj=None):
    # Methods must always be readonly
        method_fields = ("highlighted_query_note", "previous_query_notes","registration_number_display","qr_code_preview")

        if request.user.is_superuser:
            # Superuser can edit everything except the methods
            return method_fields
        else:
            # Staff: everything readonly except agent_note and status
            readonly = [f for f in self.readonly_fields if f not in ("agent_note", "status")]
            # Always include method_fields
            return list(readonly) + list(method_fields)
        
    # Actions
    actions = ["mark_approved", "mark_queried"]


    #Function to Approve application
    def mark_approved(self, request, queryset):
        for obj in queryset:
            obj.approve(staff_user=request.user)  # ✅ USE MODEL LOGIC
        self.message_user(request, "Applications approved successfully.")
    mark_approved.short_description = "Mark selected applications as Approved"

    def mark_queried(self, request, queryset):
        for obj in queryset:
            if obj.agent_note:
                obj.previous_notes.append(obj.agent_note)  # move old note to history
            # Do NOT set agent_note to hardcoded string
            obj.agent_note = ""  # leave empty for staff to type
            obj.status = Application.Status.QUERIED
            obj.save()
        self.message_user(request, f"{queryset.count()} application(s) marked as queried.")
    mark_queried.short_description = "Mark selected applications as Queried"

    # File previews
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
            return format_html('<img src="{}" width="50"/>', obj.nin.url)
        return "-"
    nin_preview.short_description = "NIN"

    def qr_code_preview(self, obj):
        if obj.qr_code:
            return format_html('<img src="{}" width="30"/>', obj.qr_code.url)
        return "-"
    qr_code_preview.short_description = "QR Code"



    # Colored status
    def colored_status(self, obj):
        color = {
            'submitted': 'gray',
            'pending': 'orange',
            'queried': 'red',
            'approved': 'green'
        }.get(obj.status, 'black')
        return format_html('<span style="color:{};">{}</span>', color, obj.get_status_display())
    colored_status.short_description = "Status"


@admin.register(SystemFee)
class SystemFeeAdmin(admin.ModelAdmin):
    list_display = (
        "name_reservation_fee",
        "application_fee",
        "updated_at",
    )

    fields = (
        "name_reservation_fee",
        "application_fee",
        "updated_at",
    )

    readonly_fields = ("updated_at",)


@admin.register(NameReservation)
class NameReservationAdmin(admin.ModelAdmin):
    list_display = (
        "reference_id",
        "proposed_name",
        "user",
        "reservation_fee",
        "status",
        "payment_reference",
        "created_at",
        "confirmed_at",
    )

    list_filter = (
        "status",
        "created_at",
        "confirmed_at",
    )

    search_fields = (
        "reference_id",
        "proposed_name",
        "user__email",
        "user__username",
        "payment_reference",
    )

    readonly_fields = (
        "reference_id",
        "user",
        "proposed_name",
        "reservation_fee",
        "payment_reference",
        "payment_submitted_at",
        "confirmed_at",
        "confirmed_by",
        "created_at",
        "updated_at",
    )


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):

    list_display = (
        "payment_reference",
        "user",
        "payment_type",
        "amount",
        "status",
        "created_at",
        "submitted_at",
        "confirmed_at",
        "confirmed_by",
    )

    list_filter = (
        "payment_type",
        "status",
        "created_at",
        "confirmed_at",
    )

    search_fields = (
        "payment_reference",
        "user__email",
        "user__username",
        "reservation__reference_id",
        "reservation__proposed_name",
    )

    readonly_fields = (
        "user",
        "payment_type",
        "reservation",
        "application",
        "amount",
        "payment_reference",
        "created_at",
        "submitted_at",
        "confirmed_at",
        "confirmed_by",
    )

    actions = ["confirm_selected_payments"]

    def save_model(self, request, obj, form, change):
        """
        Handle manual payment status changes made by staff
        inside the Django Admin.
        """

        old_status = None

        if change:
            old_obj = Payment.objects.get(pk=obj.pk)
            old_status = old_obj.status

        # Save the payment first
        super().save_model(request, obj, form, change)

    
        # =================================================
        # APPLICATION PAYMENT
        # =================================================
        if obj.payment_type == Payment.PaymentType.APPLICATION:

            application = obj.application

            if not application:
                return

            # ---------------------------------------------
            # PAYMENT CONFIRMED
            # ---------------------------------------------
            if obj.status == Payment.Status.CONFIRMED:

                if (
                    old_status != Payment.Status.CONFIRMED
                    or not obj.confirmed_at
                    or not obj.confirmed_by
                ):
                    obj.confirmed_at = timezone.now()
                    obj.confirmed_by = request.user

                    obj.save(
                        update_fields=[
                            "confirmed_at",
                            "confirmed_by",
                        ]
                    )

                # Move application to Pending Review
                if application.status != Application.Status.APPROVED:
                    application.status = Application.Status.PENDING
                    application.save(
                        update_fields=[
                            "status",
                            "updated_at",
                        ]
                    )

            # ---------------------------------------------
            # PAYMENT SUBMITTED
            # ---------------------------------------------
            elif obj.status == Payment.Status.SUBMITTED:

                obj.confirmed_at = None
                obj.confirmed_by = None

                obj.save(
                    update_fields=[
                        "confirmed_at",
                        "confirmed_by",
                    ]
                )

            # ---------------------------------------------
            # PAYMENT FAILED
            # ---------------------------------------------
            elif obj.status == Payment.Status.FAILED:

                obj.confirmed_at = None
                obj.confirmed_by = None

                obj.save(
                    update_fields=[
                        "confirmed_at",
                        "confirmed_by",
                    ]
                )

            return


        # =================================================
        # NAME RESERVATION PAYMENT
        # =================================================

        # Only synchronize name reservation payments
        if obj.payment_type != Payment.PaymentType.NAME_RESERVATION:
            return

        reservation = obj.reservation

        if not reservation:
            return

        # -------------------------------------------------
        # PAYMENT CONFIRMED
        # -------------------------------------------------
        if obj.status == Payment.Status.CONFIRMED:

            if (
                old_status != Payment.Status.CONFIRMED
                or not obj.confirmed_at
                or not obj.confirmed_by
            ):
                obj.confirmed_at = timezone.now()
                obj.confirmed_by = request.user

                obj.save(
                    update_fields=[
                        "confirmed_at",
                        "confirmed_by",
                    ]
                )

            # Officially reserve the name
            reservation.status = NameReservation.Status.RESERVED
            reservation.confirmed_at = obj.confirmed_at
            reservation.confirmed_by = request.user

            reservation.save(
                update_fields=[
                    "status",
                    "confirmed_at",
                    "confirmed_by",
                    "updated_at",
                ]
            )

        # -------------------------------------------------
        # PAYMENT SUBMITTED
        # -------------------------------------------------
        elif obj.status == Payment.Status.SUBMITTED:

            reservation.status = NameReservation.Status.PAYMENT_SUBMITTED
            reservation.confirmed_at = None
            reservation.confirmed_by = None

            reservation.save(
                update_fields=[
                    "status",
                    "confirmed_at",
                    "confirmed_by",
                    "updated_at",
                ]
            )

            obj.confirmed_at = None
            obj.confirmed_by = None

            obj.save(
                update_fields=[
                    "confirmed_at",
                    "confirmed_by",
                ]
            )

        # -------------------------------------------------
        # PAYMENT FAILED
        # -------------------------------------------------
        elif obj.status == Payment.Status.FAILED:

            reservation.status = NameReservation.Status.AWAITING_PAYMENT
            reservation.confirmed_at = None
            reservation.confirmed_by = None

            reservation.save(
                update_fields=[
                    "status",
                    "confirmed_at",
                    "confirmed_by",
                    "updated_at",
                ]
            )

            obj.confirmed_at = None
            obj.confirmed_by = None

            obj.save(
                update_fields=[
                    "confirmed_at",
                    "confirmed_by",
                ]
            )

    # -----------------------------------------------------
    # ADMIN ACTION: CONFIRM SELECTED PAYMENTS
    # -----------------------------------------------------
    @admin.action(description="Confirm selected payment(s)")
    def confirm_selected_payments(self, request, queryset):

        confirmed_count = 0
        skipped_count = 0

        for payment in queryset:

            # -------------------------------------------------
            # ONLY PROCESS SUBMITTED PAYMENTS
            # -------------------------------------------------
            if payment.status != Payment.Status.SUBMITTED:
                skipped_count += 1
                continue

            now = timezone.now()

            # =================================================
            # NAME RESERVATION PAYMENT
            # =================================================
            if payment.payment_type == Payment.PaymentType.NAME_RESERVATION:

                reservation = payment.reservation

                # Reservation must exist
                if not reservation:
                    skipped_count += 1
                    continue

                # Reservation must be awaiting confirmation
                if reservation.status != NameReservation.Status.PAYMENT_SUBMITTED:
                    skipped_count += 1
                    continue

                # Confirm payment
                payment.status = Payment.Status.CONFIRMED
                payment.confirmed_at = now
                payment.confirmed_by = request.user

                payment.save(
                    update_fields=[
                        "status",
                        "confirmed_at",
                        "confirmed_by",
                    ]
                )

                # Officially reserve the name
                reservation.status = NameReservation.Status.RESERVED
                reservation.confirmed_at = now
                reservation.confirmed_by = request.user

                reservation.save(
                    update_fields=[
                        "status",
                        "confirmed_at",
                        "confirmed_by",
                        "updated_at",
                    ]
                )

                confirmed_count += 1

            # =================================================
            # APPLICATION PAYMENT
            # =================================================
            elif payment.payment_type == Payment.PaymentType.APPLICATION:

                application = payment.application

                # Application must exist
                if not application:
                    skipped_count += 1
                    continue

                # Confirm payment
                payment.status = Payment.Status.CONFIRMED
                payment.confirmed_at = now
                payment.confirmed_by = request.user

                payment.save(
                    update_fields=[
                        "status",
                        "confirmed_at",
                        "confirmed_by",
                    ]
                )

                # Move application into Pending Review
                application.status = Application.Status.PENDING

                application.save(
                    update_fields=[
                        "status",
                        "updated_at",
                    ]
                )

                confirmed_count += 1

            else:
                skipped_count += 1

        # -----------------------------------------------------
        # SUCCESS MESSAGE
        # -----------------------------------------------------
        if confirmed_count:
            self.message_user(
                request,
                f"{confirmed_count} payment(s) confirmed successfully.",
                messages.SUCCESS,
            )

        # -----------------------------------------------------
        # SKIPPED MESSAGE
        # -----------------------------------------------------
        if skipped_count:
            self.message_user(
                request,
                f"{skipped_count} payment(s) were skipped because "
                f"they were not valid submitted payments.",
                messages.WARNING,
            )