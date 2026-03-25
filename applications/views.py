
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from .models import Application
# Create your views here.
@login_required
@require_http_methods(["GET", "POST"])
def start_application(request):
    if request.method == "GET":
        return render(request, "applications/application.html")

    # fields
    proposed_name_1 = (request.POST.get("proposed_name_1") or "").strip()
    proposed_name_2 = (request.POST.get("proposed_name_2") or "").strip()
    nature_of_business = (request.POST.get("nature_of_business") or "").strip()
    business_type = (request.POST.get("business_type") or "").strip()

    state = (request.POST.get("state") or "").strip()
    lga = (request.POST.get("lga") or "").strip()
    business_address = (request.POST.get("business_address") or "").strip()

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
        proposed_name_1=proposed_name_1,
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
    )

    if save_as_draft:
        messages.success(request, f"Draft saved. You can continue later. Ref: {app.reference_id}")
    else:
        messages.success(request, f"Application submitted successfully. Ref: {app.reference_id}")

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
            "created_at": a.created_at.isoformat(),
            "updated_at": a.updated_at.isoformat(),
        }
        for a in qs
    ]
    return JsonResponse({"applications": data})
