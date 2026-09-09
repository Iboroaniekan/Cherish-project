import hashlib
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from .models import Application,NameReservation, Payment, SystemFee
from django.template.loader import render_to_string
from django.http import FileResponse
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from weasyprint import HTML 
import uuid
from django.db.models import Q
from django.utils import timezone



# ============================================================
# NAME RESERVATION
# ============================================================

def normalize_business_name(name):
    """
    Normalize a proposed business name so that differences
    in capitalization or extra spaces cannot bypass checking.
    """
    return " ".join(
        (name or "").strip().upper().split()
    )


def is_name_available(name, exclude_reservation=None):
    """
    Check whether a business name is available.

    A name is unavailable if:
    1. It has already been officially reserved.
    2. It belongs to an approved application.

    Payment-submitted reservations do NOT permanently block
    the name until staff confirms the payment.
    """

    name = normalize_business_name(name)

    if not name:
        return False

    # Check officially reserved names
    reservation_query = NameReservation.objects.filter(
        proposed_name=name,
        status=NameReservation.Status.RESERVED
    )

    if exclude_reservation:
        reservation_query = reservation_query.exclude(
            pk=exclude_reservation.pk
        )

    if reservation_query.exists():
        return False

    # Check names already used by approved applications
    approved_application = Application.objects.filter(
        status=Application.Status.APPROVED
    ).filter(
        Q(proposed_name_1=name) |
        Q(proposed_name_2=name)
    ).exists()

    if approved_application:
        return False

    return True



@login_required
@require_http_methods(["GET", "POST"])
def name_reservation(request):
    reservations = NameReservation.objects.filter(
        user=request.user
    ).order_by("-created_at")

    context = {
        "reservations": reservations,
        "available": None,
        "checked_name": "",
        "reservation_fee": None,
    }

    # Open the reservation page
    if request.method == "GET":
        return render(
            request,
            "applications/name_reservation.html",
            context
        )

    # Get submitted values
    action = request.POST.get("action", "").strip()
    proposed_name = normalize_business_name(
        request.POST.get("proposed_name", "")
    )

    # -----------------------------------------
    # CHECK NAME AVAILABILITY
    # -----------------------------------------
    if action == "check":

        if not proposed_name:
            messages.error(
                request,
                "Please enter a proposed business name."
            )
            return redirect("applications:name_reservation")

        available = is_name_available(proposed_name)

        context["available"] = available
        context["checked_name"] = proposed_name

        if available:

            system_fee = SystemFee.objects.first()

            if not system_fee:
                messages.error(
                    request,
                    "The reservation fee has not been configured."
                )
                return redirect("applications:name_reservation")

            context["reservation_fee"] = system_fee.name_reservation_fee

        else:
            messages.error(
                request,
                f'"{proposed_name}" is not available.'
            )

        return render(
            request,
            "applications/name_reservation.html",
            context
        )

    # -----------------------------------------
    # CREATE RESERVATION
    # -----------------------------------------
    elif action == "reserve":

        if not proposed_name:
            messages.error(
                request,
                "Please enter a proposed business name."
            )
            return redirect("applications:name_reservation")

        # Check again because another user could have
        # reserved the name after the first search.
        if not is_name_available(proposed_name):
            messages.error(
                request,
                f'"{proposed_name}" is no longer available.'
            )
            return redirect("applications:name_reservation")

        system_fee = SystemFee.objects.first()

        if not system_fee:
            messages.error(
                request,
                "The reservation fee has not been configured."
            )
            return redirect("applications:name_reservation")

        fee = system_fee.name_reservation_fee

        if fee <= 0:
            messages.error(
                request,
                "The reservation fee has not been properly configured."
            )
            return redirect("applications:name_reservation")

        reservation = NameReservation.objects.create(
            user=request.user,
            proposed_name=proposed_name,
            reservation_fee=fee,
            status=NameReservation.Status.AWAITING_PAYMENT
        )

        messages.success(
            request,
            f"Please proceed to payment. "
            f"The name will only become officially reserved after your payment is confirmed by CAC staff."
        )

        return redirect(
            "applications:reservation_payment",
            reference_id=reservation.reference_id
        )

    # -----------------------------------------
    # INVALID ACTION
    # -----------------------------------------
    else:
        messages.error(
            request,
            "Invalid reservation request."
        )

        return redirect(
            "applications:name_reservation"
        )



# ------------------------------------------------------------
# SIMULATED NAME RESERVATION PAYMENT
# ------------------------------------------------------------

@login_required
@require_http_methods(["GET", "POST"])
def reservation_payment(request, reference_id):

    reservation = get_object_or_404(
        NameReservation,
        reference_id=reference_id,
        user=request.user
    )

    # Prevent paying again after payment has already been
    # submitted or the name has already been reserved.
    if reservation.status == NameReservation.Status.RESERVED:
        messages.info(
            request,
            "This name has already been reserved."
        )
        return redirect("dashboard:home")

    if reservation.status == NameReservation.Status.PAYMENT_SUBMITTED:
        messages.info(
            request,
            "Payment has already been submitted and is awaiting staff confirmation."
        )
        return redirect("dashboard:home")

    if reservation.status != NameReservation.Status.AWAITING_PAYMENT:
        messages.error(
            request,
            "This reservation is not available for payment."
        )
        return redirect("dashboard:home")

    if request.method == "GET":
        return render(
            request,
            "applications/reservation-payment.html",
            {
                "reservation": reservation
            }
        )

    # --------------------------------------------------------
    # SIMULATED PAYMENT SUBMISSION
    # --------------------------------------------------------

    payment_reference = (
        "SIM-NR-" +
        uuid.uuid4().hex[:12].upper()
    )

    payment = Payment.objects.create(
        user=request.user,
        payment_type=Payment.PaymentType.NAME_RESERVATION,
        reservation=reservation,
        amount=reservation.reservation_fee,
        payment_reference=payment_reference,
        status=Payment.Status.SUBMITTED,
        submitted_at=timezone.now()
    )

    reservation.payment_reference = payment_reference
    reservation.payment_submitted_at = timezone.now()
    reservation.status = NameReservation.Status.PAYMENT_SUBMITTED
    reservation.save(
        update_fields=[
            "payment_reference",
            "payment_submitted_at",
            "status",
            "updated_at",
        ]
    )

    messages.success(
        request,
        "Payment submitted successfully. "
        "Your name will only become officially reserved after staff confirms the payment."
    )

    return redirect("applications:reservation_payment_status",reference_id=reservation.reference_id)




@login_required
@require_http_methods(["GET"])
def reservation_payment_status(request, reference_id):
    reservation = get_object_or_404(
    NameReservation,
    reference_id=reference_id,
    user=request.user
    )


    payment = Payment.objects.filter(
        reservation=reservation,
        payment_type=Payment.PaymentType.NAME_RESERVATION
    ).order_by("-created_at").first()

    if not payment:
        messages.info(
            request,
            "No payment has been submitted for this reservation yet."
        )
        return redirect(
            "applications:reservation_payment",
            reference_id=reservation.reference_id
        )

    return render(
        request,
        "applications/reservation-payment-status.html",
        {
            "reservation": reservation,
            "payment": payment,
        }
    )

# ------------------------------------------------------------
# SIMULATED APPLICATION PAYMENT
# ------------------------------------------------------------
@login_required
@require_http_methods(["GET", "POST"])
def application_payment(request, reference_id):
    application = get_object_or_404(
        Application,
        reference_id=reference_id,
        user=request.user
    )

    # Get the application fee
    system_fee = SystemFee.objects.first()

    if not system_fee:
        messages.error(
            request,
            "The application fee has not been configured."
        )
        return redirect("dashboard:home")

    application_fee = system_fee.application_fee

    if application_fee <= 0:
        messages.error(
            request,
            "The application fee has not been properly configured."
        )
        return redirect("dashboard:home")

    # Get the latest application payment
    existing_payment = Payment.objects.filter(
        application=application,
        payment_type=Payment.PaymentType.APPLICATION
    ).order_by("-created_at").first()

    # --------------------------------------------------------
    # PAYMENT ALREADY CONFIRMED
    # --------------------------------------------------------
    if existing_payment and existing_payment.status == Payment.Status.CONFIRMED:
        messages.info(
            request,
            "Payment for this application has already been confirmed."
        )
        return redirect("dashboard:home")

    # --------------------------------------------------------
    # PAYMENT ALREADY SUBMITTED
    # --------------------------------------------------------
    if existing_payment and existing_payment.status == Payment.Status.SUBMITTED:
        messages.info(
            request,
            "Payment has already been submitted and is awaiting staff confirmation."
        )
        return redirect(
            "applications:application_payment_status",
            reference_id=application.reference_id
        )

    # --------------------------------------------------------
    # SHOW PAYMENT PAGE
    # --------------------------------------------------------
    if request.method == "GET":
        return render(
            request,
            "applications/application-payment.html",
            {
                "application": application,
                "application_fee": application_fee,
                "payment": existing_payment,
            }
        )

    # --------------------------------------------------------
    # SIMULATED PAYMENT SUBMISSION
    # --------------------------------------------------------

    if existing_payment:
        # Change the existing PENDING payment to SUBMITTED
        existing_payment.status = Payment.Status.SUBMITTED
        existing_payment.submitted_at = timezone.now()
        existing_payment.amount = application_fee

        if not existing_payment.payment_reference:
            existing_payment.payment_reference = (
                "SIM-APP-" +
                uuid.uuid4().hex[:12].upper()
            )

        existing_payment.save()

        payment = existing_payment

    else:
        # Create a payment only if one does not already exist
        payment_reference = (
            "SIM-APP-" +
            uuid.uuid4().hex[:12].upper()
        )

        payment = Payment.objects.create(
            user=request.user,
            payment_type=Payment.PaymentType.APPLICATION,
            application=application,
            amount=application_fee,
            payment_reference=payment_reference,
            status=Payment.Status.SUBMITTED,
            submitted_at=timezone.now()
        )


    return redirect(
        "applications:application_payment_status",
        reference_id=application.reference_id
    )

@login_required
@require_http_methods(["GET"])
def application_payment_status(request, reference_id):

    application = get_object_or_404(
        Application,
        reference_id=reference_id,
        user=request.user
    )

    payment = Payment.objects.filter(
        application=application,
        payment_type=Payment.PaymentType.APPLICATION
    ).order_by("-created_at").first()

    if not payment:
        messages.info(
            request,
            "No payment has been submitted for this application yet."
        )

        return redirect(
            "applications:application_payment",
            reference_id=application.reference_id
        )

    return render(
        request,
        "applications/application-payment-status.html",
        {
            "application": application,
            "payment": payment,
        }
    )

# ============================================================
# START BUSINESS REGISTRATION APPLICATION
# ============================================================

@login_required
@require_http_methods(["GET", "POST"])
def start_application(request):

    # ------------------------------------------------------------
    # GET THE USER'S LATEST CONFIRMED NAME RESERVATION
    # ------------------------------------------------------------

    confirmed_reservation = (
        NameReservation.objects
        .filter(
            user=request.user,
            status=NameReservation.Status.RESERVED,
            application__isnull=True
        )
        .order_by("-confirmed_at")
        .first()
    )

    # A user cannot start an application without a confirmed name
    if not confirmed_reservation:
        messages.error(
            request,
            "You must have a confirmed business name reservation before starting an application."
        )
        return redirect("applications:name_reservation")

    # ------------------------------------------------------------
    # GET REQUEST
    # ------------------------------------------------------------

    if request.method == "GET":
        return render(
            request,
            "applications/application.html",
            {
                "confirmed_reservation": confirmed_reservation
            }
        )

    # ------------------------------------------------------------
    # FORM DATA
    # ------------------------------------------------------------

    # Option 1 MUST come from the confirmed reservation.
    # We do NOT trust the value submitted by the browser.
    proposed_name_1 = normalize_business_name(
        confirmed_reservation.proposed_name
    )

    proposed_name_2 = normalize_business_name(
        request.POST.get("proposed_name_2", "")
    )

    nature_of_business = (
        request.POST.get("nature_of_business") or ""
    ).strip()

    business_type = (
        request.POST.get("business_type") or ""
    ).strip()

    state = (
        request.POST.get("state") or ""
    ).strip().upper()

    lga = (
        request.POST.get("lga") or ""
    ).strip().upper()

    business_address = (
        request.POST.get("business_address") or ""
    ).strip().upper()

    owner_first_name = (
        request.POST.get("owner_first_name") or ""
    ).strip()

    owner_last_name = (
        request.POST.get("owner_last_name") or ""
    ).strip()

    owner_email = (
        request.POST.get("owner_email") or ""
    ).strip()

    owner_phone = (
        request.POST.get("owner_phone") or ""
    ).strip()

    business_description = (
        request.POST.get("business_description") or ""
    ).strip()

    confirm = request.POST.get("confirm")

    passport = request.FILES.get("passport")
    signature = request.FILES.get("signature")
    nin = request.FILES.get("nin")

    save_as_draft = request.POST.get("save_as_draft") == "1"

    # ------------------------------------------------------------
    # RECHECK RESERVATION BEFORE CREATING APPLICATION
    # ------------------------------------------------------------

    confirmed_reservation.refresh_from_db()

    if confirmed_reservation.status != NameReservation.Status.RESERVED:
        messages.error(
            request,
            "Your business name reservation is no longer confirmed. "
            "Please check your name reservation status."
        )
        return redirect("applications:name_reservation")

    # ------------------------------------------------------------
    # PREVENT ONE RESERVATION FROM BEING USED TWICE
    # ------------------------------------------------------------

    existing_application = Application.objects.filter(
        name_reservation=confirmed_reservation
    ).first()

    if existing_application:
        messages.info(
            request,
            f"This reserved business name has already been used for application "
            f"{existing_application.reference_id}."
        )
        return redirect("dashboard:home")

    # ------------------------------------------------------------
    # VALIDATION
    # ------------------------------------------------------------

    errors = []

    if not save_as_draft:

        if not proposed_name_1:
            errors.append(
                "Your confirmed business name is required."
            )

        if not nature_of_business:
            errors.append(
                "Nature of Business is required."
            )

        if not business_type:
            errors.append(
                "Business Type is required."
            )

        if not state:
            errors.append(
                "State is required."
            )

        if not lga:
            errors.append(
                "LGA is required."
            )

        if not business_address:
            errors.append(
                "Business Address is required."
            )

        if not owner_first_name:
            errors.append(
                "Owner First Name is required."
            )

        if not owner_last_name:
            errors.append(
                "Owner Last Name is required."
            )

        if not owner_email:
            errors.append(
                "Owner Email is required."
            )

        if not owner_phone:
            errors.append(
                "Owner Phone is required."
            )

        if not passport:
            errors.append(
                "Passport Photograph is required."
            )

        if not signature:
            errors.append(
                "Signature is required."
            )

        if not nin:
            errors.append(
                "NIN Slip is required."
            )

        if not confirm:
            errors.append(
                "You must confirm that the information is correct."
            )

    if errors:
        for error in errors:
            messages.error(request, error)

        return render(
            request,
            "applications/application.html",
            {
                "confirmed_reservation": confirmed_reservation
            }
        )

    # ------------------------------------------------------------
    # GET APPLICATION FEE
    # ------------------------------------------------------------

    system_fee = SystemFee.objects.first()

    if not system_fee:
        messages.error(
            request,
            "The application fee has not been configured."
        )
        return redirect("dashboard:home")

    application_fee = system_fee.application_fee

    if not application_fee or application_fee <= 0:
        messages.error(
            request,
            "The application fee has not been properly configured."
        )
        return redirect("dashboard:home")

    # ------------------------------------------------------------
    # CREATE APPLICATION
    # ------------------------------------------------------------

    if save_as_draft:
        status = Application.Status.PENDING
    else:
        status = Application.Status.SUBMITTED

    app = Application.objects.create(
        user=request.user,

        # Link application to the officially reserved name
        name_reservation=confirmed_reservation,

        # Option 1 comes ONLY from confirmed reservation
        proposed_name_1=proposed_name_1,

        # Option 2 is optional
        proposed_name_2=proposed_name_2,

        nature_of_business=nature_of_business,
        business_type=business_type,

        state=state,
        lga=lga,
        business_address=business_address,

        owner_first_name=owner_first_name,
        owner_last_name=owner_last_name,
        owner_email=owner_email,
        owner_phone=owner_phone,

        business_description=business_description,

        passport=passport,
        signature=signature,
        nin=nin,

        status=status
    )

    # ------------------------------------------------------------
    # DRAFT
    # ------------------------------------------------------------

    if save_as_draft:

        messages.success(
            request,
            f"Draft saved successfully. Ref: {app.reference_id}"
        )

        return redirect("dashboard:home")

    # ------------------------------------------------------------
    # CREATE APPLICATION PAYMENT
    # ------------------------------------------------------------

    payment_reference = (
        "SIM-APP-" +
        uuid.uuid4().hex[:12].upper()
    )

    Payment.objects.create(
        user=request.user,
        payment_type=Payment.PaymentType.APPLICATION,
        application=app,
        amount=application_fee,
        payment_reference=payment_reference,
        status=Payment.Status.PENDING
    )


    # ------------------------------------------------------------
    # SEND USER TO APPLICATION PAYMENT
    # ------------------------------------------------------------

    return redirect(
        "applications:application_payment",
        reference_id=app.reference_id
    )




@login_required
def my_applications_api(request):
    qs = Application.objects.filter(user=request.user).order_by("-created_at")
    data = [
        {
            "reference_id": a.reference_id,
            "business_name": a.proposed_name_1,
            "status": a.status,
            "status_label": a.get_status_display(),
            "agent_note": a.agent_note,
            "previous_notes": a.previous_notes,
            "created_at": a.created_at.isoformat(),
            "updated_at": a.updated_at.isoformat(),
        }
        for a in qs
    ]
    return JsonResponse({"applications": data})


# Function to Modify Submitted Application
@login_required
@require_http_methods(["GET", "POST"])
def modify_application(request, reference_id):

    app = get_object_or_404(
        Application,
        reference_id=reference_id,
        user=request.user
    )

    # Only queried applications can be modified
    if app.status != Application.Status.QUERIED:
        messages.error(
            request,
            "You cannot modify this application."
        )
        return redirect("dashboard:home")

    # ------------------------------------------------------------
    # GET REQUEST
    # ------------------------------------------------------------

    if request.method == "GET":
        return render(
            request,
            "applications/modify-application.html",
            {
                "app": app,
                "reserved_name": (
                    app.name_reservation.proposed_name
                    if app.name_reservation
                    else app.proposed_name_1
                ),
            }
        )

    # ------------------------------------------------------------
    # KEEP PROPOSED NAME FROM THE OFFICIAL RESERVATION
    # ------------------------------------------------------------

    if app.name_reservation:
        app.proposed_name_1 = normalize_business_name(
            app.name_reservation.proposed_name
        )
    else:
        app.proposed_name_1 = normalize_business_name(
            app.proposed_name_1
        )

    # ------------------------------------------------------------
    # UPDATE OTHER FIELDS
    # ------------------------------------------------------------

    app.proposed_name_2 = normalize_business_name(
        request.POST.get("proposed_name_2", "")
    )

    app.nature_of_business = (
        request.POST.get("nature_of_business") or ""
    ).strip()

    app.business_type = (
        request.POST.get("business_type") or ""
    ).strip()

    app.state = (
        request.POST.get("state") or ""
    ).strip().upper()

    app.lga = (
        request.POST.get("lga") or ""
    ).strip().upper()

    app.business_address = (
        request.POST.get("business_address") or ""
    ).strip().upper()

    app.owner_first_name = (
        request.POST.get("owner_first_name") or ""
    ).strip()

    app.owner_last_name = (
        request.POST.get("owner_last_name") or ""
    ).strip()

    app.owner_email = (
        request.POST.get("owner_email") or ""
    ).strip()

    app.owner_phone = (
        request.POST.get("owner_phone") or ""
    ).strip()

    app.business_description = (
        request.POST.get("business_description") or ""
    ).strip()

    # ------------------------------------------------------------
    # FILE UPDATES
    # ------------------------------------------------------------

    if request.FILES.get("passport"):
        app.passport = request.FILES.get("passport")

    if request.FILES.get("signature"):
        app.signature = request.FILES.get("signature")

    if request.FILES.get("nin"):
        app.nin = request.FILES.get("nin")

    # ------------------------------------------------------------
    # VALIDATION
    # ------------------------------------------------------------

    errors = []

    required_fields = [
        ("proposed_name_1", "Proposed Business Name"),
        ("nature_of_business", "Nature of Business"),
        ("business_type", "Business Type"),
        ("state", "State"),
        ("lga", "LGA"),
        ("business_address", "Business Address"),
        ("owner_first_name", "Owner First Name"),
        ("owner_last_name", "Owner Last Name"),
        ("owner_email", "Owner Email"),
        ("owner_phone", "Owner Phone"),
    ]

    for field, label in required_fields:
        if not getattr(app, field):
            errors.append(
                f"{label} is required."
            )

    if errors:
        for error in errors:
            messages.error(request, error)

        return render(
            request,
            "applications/modify-application.html",
            {
                "app": app,
                "reserved_name": (
                    app.name_reservation.proposed_name
                    if app.name_reservation
                    else app.proposed_name_1
                ),
            }
        )

    # ------------------------------------------------------------
    # SAVE CORRECTIONS
    # ------------------------------------------------------------

    app.clear_query_note()

    messages.success(
        request,
        "Application corrected and resubmitted successfully."
    )

    return redirect("dashboard:home")

#Function to download certificate
#@login_required
#def download_certificate(request, reference_id):
  #  application = get_object_or_404(
  #      Application,
   #     reference_id=reference_id,
   #     user=request.user
   # )
    # 🚨 Only approved applications can download
 #   if application.status != Application.Status.APPROVED:
 #       return HttpResponse("Certificate not available", status=403)
 #   html_string = render_to_string("certificate/certificate.html", {
 #   "application": application
#})
   # response = HttpResponse(content_type="application/pdf")
    #response['Content-Disposition'] = f'attachment; filename="certificate_{application.registration_number}.pdf"'

  #HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf(response)
   # return response


  
#Function to download certificate for the user when authenticated 
@login_required
def download_certificate(request, reference_id):
    application = get_object_or_404(
        Application,
        reference_id=reference_id,
        user=request.user
    )

    if application.status != Application.Status.APPROVED:
        return HttpResponse("Certificate not available", status=403)

    if not application.certificate:
        return HttpResponse("Certificate file not found.", status=404)

    return FileResponse(
        application.certificate.open("rb"),
        as_attachment=True,
        filename=f"certificate_{application.registration_number}.pdf",
    )

# Function to view certificate when authenticated
@login_required
def view_certificate(request, reference_id):
    application = get_object_or_404(
        Application,
        reference_id=reference_id,
        user=request.user
    )

    if application.status != Application.Status.APPROVED:
        return render(request, "error.html", {
            "message": "Certificate not available"
        })

    return render(request, "certificate/certificate.html", {
        "application": application
    })

#Function to Verify Certificate for the qrcode
@csrf_exempt
def verify_certificate(request,token):
    token = request.GET.get("token")
    
    valid = False
    application = None
    qr_code_url = None
    try:
        application = Application.objects.get(
            verification_token=token,
            status=Application.Status.APPROVED
        )
        # Recalculate signature
        data = f"{application.registration_number}{application.proposed_name_1}{application.owner_first_name}{application.owner_last_name}{application.approved_at}"
        recalculated_signature = hashlib.sha256(data.encode("utf-8")).hexdigest()

        # Check integrity
        if recalculated_signature == application.digital_signature:
            valid = True
        
        if application.qr_code:
            qr_code_url =application.qr_code.url
        else:
            valid = False
            
    except Application.DoesNotExist:
        application = None
        valid = False
        qr_code_url = None
        

    return render(request, "certificate/verify.html", {
        "application": application,
        "valid": valid,
        "qr_code_url":qr_code_url
    })

# Function to verify the certificate publicly using RC-NUMBER
def public_search(request):
    reg_number = request.GET.get("registration_number", "").strip()
    application = None
    valid = False
    qr_code_url = None

    if reg_number:
        try:
            application = Application.objects.get(
                registration_number=reg_number,
                status=Application.Status.APPROVED
            )

            # Recalculate signature for tamper-proof check
            data = f"{application.registration_number}{application.proposed_name_1}{application.owner_first_name}{application.owner_last_name}{application.approved_at}"
            recalculated_signature = hashlib.sha256(data.encode("utf-8")).hexdigest()
            valid = recalculated_signature == application.digital_signature

            if application.qr_code:
                qr_code_url = application.qr_code.url

        except Application.DoesNotExist:
            application = None
            valid = False
            qr_code_url = None

    return render(request, "frontend/index.html", {
        "application": application,
        "valid": valid,
        "qr_code_url": qr_code_url,
        "search_query": reg_number,
    })

#Function to display the certificate after verification
def public_certificate(request, token):
    application = get_object_or_404(
        Application,
        verification_token=token,
        status=Application.Status.APPROVED
    )

    return render(
        request,
        "certificate/certificate.html",
        {
            "application": application
        }
    )