from xml.parsers.expat import errors
from django.shortcuts import render,redirect
from django.contrib.messages import get_messages
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login as auth_login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.views.decorators.http import require_http_methods
from .models import Profile



User = get_user_model()
# Create your views here.
@require_http_methods(["GET", "POST"])
def signup(request):
    list(get_messages(request))
    if request.method == "GET":
        formdata = request.session.pop("signup_formdata", None)
        ctx = {"formdata": formdata} if formdata else {}
        return render(request, 'accounts/signup.html', ctx)

    # Read form fields (must match your HTML name="")
    first_name = (request.POST.get("first_name") or "").strip()
    last_name = (request.POST.get("last_name") or "").strip()
    email = (request.POST.get("email") or "").strip().lower()
    phone_number = (request.POST.get("phone_number") or "").strip()          # stored later (Profile)
    account_type = (request.POST.get("account_type") or "").strip()  # stored later (Profile)
    password1 = request.POST.get("password1") or ""
    password2 = request.POST.get("password2") or ""
    terms = request.POST.get("terms")

    # For repopulating fields on error
    context = {
        "formdata": {
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "phone_number": phone_number,
            "account_type": account_type,
            "terms": bool(terms),
        }
    }
    errors = []

    if not account_type:
        errors.append("Please select an account type.")
    if not first_name:
        errors.append("First name is required.")
    if not last_name:
        errors.append("Last name is required.")
    if not email:
        errors.append("Email is required.")
    if not phone_number:
        errors.append("Phone number is required.")
    if not terms:
        errors.append("You must accept the terms to continue.")
    if password1 != password2:
        errors.append("Passwords do not match.")
    
      # Email uniqueness
    if User.objects.filter(username=email).exists() or User.objects.filter(email=email).exists():
        errors.append("An account with this email already exists.")

    # Django password validators (length/common password/etc)
    if password1 and not errors:
        try:
            validate_password(password1)
        except ValidationError as e:
            errors.extend(e.messages)
    if errors:
        for e in errors:
            messages.error(request, e)
        request.session["signup_formdata"] = context["formdata"]
        return redirect("accounts:signup")

    # Create a NORMAL user (not staff)
    user = User.objects.create_user(
        username=email,     # using email as username for simplicity
        email=email,
        password=password1,
        first_name=first_name,
        last_name=last_name,
        is_staff=False,
        is_superuser=False,
    )
    Profile.objects.create(
    user=user,
    phone_number=phone_number,
    account_type=account_type,
)
    messages.success(request, "Account created successfully. Please log in.")
    return redirect("accounts:login")



@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.method == "GET":
        formdata = request.session.pop("login_formdata", None)
        ctx = {"formdata": formdata} if formdata else {}
        return render(request, "accounts/login.html", ctx)
    email = (request.POST.get("email") or "").strip().lower()
    password = request.POST.get("password") or ""
    user = authenticate(request, username=email, password=password)
    if user is None and "@" in email:
        try:
            u = User.objects.get(email__iexact=email)
            user = authenticate(request, username=u.username, password=password)
        except User.DoesNotExist:
            user = None
    if user is None:
        messages.error(request, "Invalid email or password.")
        request.session["login_formdata"] = {"email": email}
        return redirect("accounts:login")
    auth_login(request, user)
     # ✅ Redirect rule
    if user.is_staff:
        return redirect("/admin/")     # Django admin
    return redirect("dashboard:home")      # Normal user dashboard


def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("accounts:login")
    