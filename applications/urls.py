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
    path("certificate/public/<str:token>/",views.public_certificate,name="public_certificate"),
    path("name-reservation/", views.name_reservation, name="name_reservation" ),
    path("name-reservation/payment/<str:reference_id>/", views.reservation_payment, name="reservation_payment" ),
    path("reservation-payment-status/<str:reference_id>/",views.reservation_payment_status, name="reservation_payment_status"),
    path("application-payment/<str:reference_id>/",views.application_payment,name="application_payment"),
    path("application-payment-status/<str:reference_id>/", views.application_payment_status,name="application_payment_status")
   

]
