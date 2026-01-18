
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect



# Create your views here.
@login_required
def home(request):
    # If a staff user tries to access user dashboard, send them to admin
    if request.user.is_staff:
        return redirect("/admin/")
    return render(request, "dashboard/dashboard.html")
