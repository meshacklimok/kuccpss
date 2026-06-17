from django.urls import path
from . import views

app_name = "payments"

urlpatterns = [
    path("required/", views.payment_required, name="payment_required"),
    path("history/", views.payment_history, name="payment_history"),
    path("initiate/", views.initiate_payment, name="initiate_payment"),
    path("webhook/mpesa/", views.mpesa_webhook, name="mpesa_webhook"),
    path("status/<int:payment_id>/", views.payment_status, name="payment_status"),
]
