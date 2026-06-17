from django.urls import path
from . import views

app_name = "predictor"

urlpatterns = [
    path("",           views.predictor_index, name="index"),
    path("pdf/quick/", views.quick_pdf,       name="quick_pdf"),
    path("pdf/report/",views.full_report_pdf,  name="full_report"),
]
