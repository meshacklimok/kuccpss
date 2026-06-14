from django.urls import path
from . import views

app_name = "payments"

urlpatterns = [
    path("required/", views.payment_required, name="payment_required"),
    path("history/", views.payment_history, name="payment_history"),
]
