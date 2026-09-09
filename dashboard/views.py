from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

from applications.models import NameReservation


# Create your views here.
@login_required
def home(request):
    # If a staff user tries to access user dashboard, send them to admin
    if request.user.is_staff:
        return redirect("/admin/")

    # Check whether the user has at least one officially confirmed
    # business name reservation.
    confirmed_reservation = (
        NameReservation.objects
        .filter(
            user=request.user,
            status=NameReservation.Status.RESERVED
        )
        .order_by("-confirmed_at")
        .first()
    )

    return render(
        request,
        "dashboard/dashboard.html",
        {
            "confirmed_reservation": confirmed_reservation,
            "has_reserved_name": confirmed_reservation is not None,
        }
    )