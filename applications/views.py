import hashlib
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from .models import Application 
from django.template.loader import render_to_string
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from weasyprint import HTML # type: ignore

@login_required
@require_http_methods(["GET", "POST"])
def start_application(request):
    if request.method == "GET":
        return render(request, "applications/application.html")

    proposed_name_1 = (request.POST.get("proposed_name_1") or "").strip().upper()
    proposed_name_2 = (request.POST.get("proposed_name_2") or "").strip().upper()
    nature_of_business = (request.POST.get("nature_of_business") or "").strip()
    business_type = (request.POST.get("business_type") or "").strip()
    state = (request.POST.get("state") or "").strip().upper()
    lga = (request.POST.get("lga") or "").strip().upper()
    business_address = (request.POST.get("business_address") or "").strip().upper()
    owner_first_name = (request.POST.get("owner_first_name") or "").strip()
    owner_last_name = (request.POST.get("owner_last_name") or "").strip()
    owner_email = (request.POST.get("owner_email") or "").strip()
    owner_phone = (request.POST.get("owner_phone") or "").strip()
    business_description = (request.POST.get("business_description") or "").strip()
    confirm = request.POST.get("confirm")
    passport = request.FILES.get("passport")
    signature = request.FILES.get("signature")
    nin = request.FILES.get("nin")
    save_as_draft = request.POST.get("save_as_draft") == "1"
    status = Application.Status.PENDING if save_as_draft else Application.Status.SUBMITTED

    errors = []
    if not save_as_draft:
        if not proposed_name_1: errors.append("Proposed Business Name (Option 1) is required.")
        if not nature_of_business: errors.append("Nature of Business is required.")
        if not business_type: errors.append("Business Type is required.")
        if not state: errors.append("State is required.")
        if not lga: errors.append("LGA is required.")
        if not business_address: errors.append("Business Address is required.")
        if not owner_first_name: errors.append("Owner First Name is required.")
        if not owner_last_name: errors.append("Owner Last Name is required.")
        if not owner_email: errors.append("Owner Email is required.")
        if not owner_phone: errors.append("Owner Phone is required.")
        if not passport: errors.append("Passport Photograph is required.")
        if not signature: errors.append("Signature is required.")
        if not nin: errors.append("NIN Slip is required.")
        if not confirm: errors.append("You must confirm that the information is correct.")

    if errors:
        for e in errors:
            messages.error(request, e)
        return redirect("applications:start")

    app = Application.objects.create(
        user=request.user,
        proposed_name_1=proposed_name_1.upper(),
        proposed_name_2=proposed_name_2.upper(),
        nature_of_business=nature_of_business,
        business_type=business_type,
        state=state.upper(),
        lga=lga.upper(),
        business_address=business_address.upper(),
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

    msg = f"Draft saved. Ref: {app.reference_id}" if save_as_draft else f"Application submitted successfully. Ref: {app.reference_id}"
    messages.success(request, msg)
    return redirect("dashboard:home")


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


@login_required
@require_http_methods(["GET", "POST"])
def modify_application(request, reference_id):
    app = get_object_or_404(Application, reference_id=reference_id, user=request.user)

    if app.status != Application.Status.QUERIED:
        messages.error(request, "You cannot modify this application.")
        return redirect("dashboard:home")

    if request.method == "GET":
        return render(request, "applications/modify-application.html", {"app": app})

    # Update fields
    app.proposed_name_1 = (request.POST.get("proposed_name_1") or "").strip().upper()
    app.proposed_name_2 = (request.POST.get("proposed_name_2") or "").strip().upper()
    app.nature_of_business = (request.POST.get("nature_of_business") or "").strip()
    app.business_type = (request.POST.get("business_type") or "").strip()
    app.state = (request.POST.get("state") or "").strip().upper()
    app.lga = (request.POST.get("lga") or "").strip().upper()
    app.business_address = (request.POST.get("business_address") or "").strip().upper()
    app.owner_first_name = (request.POST.get("owner_first_name") or "").strip()
    app.owner_last_name = (request.POST.get("owner_last_name") or "").strip()
    app.owner_email = (request.POST.get("owner_email") or "").strip()
    app.owner_phone = (request.POST.get("owner_phone") or "").strip()
    app.business_description = (request.POST.get("business_description") or "").strip()

    # File updates
    if request.FILES.get("passport"): app.passport = request.FILES.get("passport")
    if request.FILES.get("signature"): app.signature = request.FILES.get("signature")
    if request.FILES.get("nin"): app.nin = request.FILES.get("nin")

    # Validation
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
            errors.append(f"{label} is required.")

    if errors:
        for e in errors:
            messages.error(request, e)
        return render(request, "applications/modify-application.html", {"app": app})

    # Reset status, clear active query note
    app.clear_query_note()
    messages.success(request, "Application corrected and resubmitted successfully.")
    return redirect("dashboard:home")

@login_required
def download_certificate(request, reference_id):
    application = get_object_or_404(
        Application,
        reference_id=reference_id,
        user=request.user
    )
    # 🚨 Only approved applications can download
    if application.status != Application.Status.APPROVED:
        return HttpResponse("Certificate not available", status=403)
    html_string = render_to_string("certificate/certificate.html", {
    "application": application
})
    response = HttpResponse(content_type="application/pdf")
    response['Content-Disposition'] = f'attachment; filename="certificate_{application.registration_number}.pdf"'

    HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf(response)

    return response

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