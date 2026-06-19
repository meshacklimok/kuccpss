from django.urls import path
from . import views

app_name = "mentorship"

urlpatterns = [
    path("", views.directory, name="directory"),
    path("become-mentor/", views.become_mentor, name="become_mentor"),
    path("become-mentor/success/", views.become_mentor_success, name="become_mentor_success"),
    path("dashboard/", views.mentor_dashboard, name="dashboard"),
    path("dashboard/slots/add/", views.add_slots, name="add_slots"),
    path("dashboard/slots/<int:slot_id>/delete/", views.delete_slot, name="delete_slot"),
    path("mentor/<int:mentor_pk>/", views.mentor_profile, name="mentor_profile"),
    path("mentor/<int:mentor_pk>/book/", views.book_session, name="book_session"),
    path("checkout/<uuid:token>/", views.checkout, name="checkout"),
    path("checkout/<uuid:token>/pay/", views.initiate_payment, name="initiate_payment"),
    path("webhook/payment/", views.payment_webhook, name="payment_webhook"),
    path("checkout/<uuid:token>/status/", views.session_status, name="session_status"),
    path("dashboard/edit/", views.edit_mentor_profile, name="edit_profile"),
    path("session/<uuid:token>/", views.session_detail, name="session_detail"),
    path("session/<uuid:token>/complete/", views.complete_session, name="complete_session"),
    path("session/<uuid:token>/rate/", views.rate_session, name="rate_session"),
    path("session/<uuid:token>/cancel/", views.cancel_session, name="cancel_session"),
    path("my-sessions/", views.my_sessions, name="my_sessions"),
    path("session/<uuid:token>/calendar.ics", views.download_ics, name="download_ics"),
    path("dashboard/withdraw/", views.request_withdrawal, name="request_withdrawal"),
    path("dashboard/withdraw-application/", views.withdraw_application, name="withdraw_application"),
]
