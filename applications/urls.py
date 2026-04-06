from django.urls import path
from . import views

app_name = "applications"

urlpatterns = [
    path("start/", views.start_application, name="start"),
    path("api/mine/", views.my_applications_api, name="api_mine"),
    path("modify/<str:reference_id>/", views.modify_application, name="modify"),
    path("certificate/<str:reference_id>/",views.download_certificate, name="download_certificate" ),
    path("certificate/view/<str:reference_id>/", views.view_certificate, name="view_certificate"),
    path("verify/<str:token>/", views.verify_certificate, name="verify_certificate"),
    path('public-search/', views.public_search, name='public_search'),
]
