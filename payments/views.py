from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Payment


@login_required
def payment_required(request):
    feature = request.GET.get("feature", "")
    return render(request, "payments/payment_required.html", {"feature": feature})


@login_required
def payment_history(request):
    payments = Payment.objects.filter(user=request.user)
    return render(request, "payments/payment_history.html", {"payments": payments})
