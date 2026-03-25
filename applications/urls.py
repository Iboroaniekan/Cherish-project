from django.urls import path
from . import views

app_name = "applications"

urlpatterns = [
    path("start/", views.start_application, name="start"),
    path("api/mine/", views.my_applications_api, name="api_mine"),
]
