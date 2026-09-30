"""
Admin smoke tests: every registered admin page renders, and the admin actions that
affect users actually reach them (unlocks, emails, wallet changes, confirmations).
"""
import datetime
from unittest import mock

from django.contrib import admin
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import NoReverseMatch, reverse

from accounts.models import AffiliateProfile, AffiliateWithdrawalRequest, EmailBroadcast, User

STATIC_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(STORAGES=STATIC_STORAGES, STAFF_2FA_REQUIRED=False)  # 2FA covered in test_security
class AdminSmokeTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(email="admin@example.com", password="pw-Admin-123")
        self.client.force_login(self.admin_user)
        self.student = User.objects.create_user(email="student@example.com", password="pw-Student-123", is_verified=True)

    def _action(self, model, action, pks):
        url = reverse(f"admin:{model._meta.app_label}_{model._meta.model_name}_changelist")
        return self.client.post(url, {"action": action, "_selected_action": [str(pk) for pk in pks]}, follow=True)

    def _messages(self, response):
        return [str(m) for m in response.context["messages"]]

    def test_every_admin_changelist_and_add_page_renders(self):
        failures = []
        for model in admin.site._registry:
            info = (model._meta.app_label, model._meta.model_name)
            for name in ("changelist", "add"):
                try:
                    url = reverse("admin:%s_%s_%s" % (*info, name))
                except NoReverseMatch:
                    continue
                resp = self.client.get(url)
                # 302 = singleton configs redirecting to their change page; 403 = add disabled.
                if resp.status_code not in (200, 302, 403):
                    failures.append(f"{url} -> {resp.status_code}")
        self.assertEqual(failures, [])

    def test_mark_payment_completed_unlocks_feature_and_sends_receipt(self):
        from career.models import AIChatCredit
        from payments.models import Payment
        payment = Payment.objects.create(user=self.student, feature="ai_chat_access", amount=50, status="pending")
        resp = self._action(Payment, "mark_completed", [payment.pk])
        payment.refresh_from_db()
        self.assertEqual(payment.status, "completed")
        self.assertGreater(AIChatCredit.for_user(self.student).paid_messages_remaining, 0)
        self.assertTrue(any(self.student.email in m.to for m in mail.outbox))
        self.assertTrue(any("1 payment(s) marked as completed" in m for m in self._messages(resp)))

    def test_suspend_reports_count_and_signs_user_out(self):
        student_client = self.client_class()
        student_client.force_login(self.student)
        resp = self._action(User, "suspend_users", [self.student.pk, self.admin_user.pk])
        self.assertTrue(any("1 user(s) suspended" in m for m in self._messages(resp)))
        self.admin_user.refresh_from_db()
        self.assertFalse(self.admin_user.is_suspended)  # can't lock yourself out
        r = student_client.get("/")
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("accounts:login"), r["Location"])

    def test_broadcast_requires_confirmation_and_sends_once(self):
        b = EmailBroadcast.objects.create(subject="Hello", heading="Hi", body="Line one")
        url = reverse("admin:emailbroadcast_send", args=[b.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Yes, send to")
        self.assertEqual(len(mail.outbox), 0)
        # Run the background delivery inline so the test DB transaction sees it.
        with mock.patch("accounts.admin._start_background", side_effect=lambda fn, *a: fn(*a)), \
                self.captureOnCommitCallbacks(execute=True):
            resp = self.client.post(url, follow=True)
            self.client.post(url)  # double submit
        self.assertTrue(any("sending in the background" in m for m in self._messages(resp)))
        b.refresh_from_db()
        self.assertEqual(b.status, "sent")
        self.assertEqual(b.recipient_count, 2)
        self.assertEqual(len(mail.outbox), 1)

    def test_commission_payout_records_withdrawal_and_debits_once(self):
        from accounts.models import AffiliateCommission
        from payments.models import Payment
        aff = AffiliateProfile.objects.create(user=self.student, wallet_balance=30)
        ids = []
        for amount in (10, 20):
            payer = User.objects.create_user(email=f"payer{amount}@example.com", password="pw-Payer-123")
            pay = Payment.objects.create(user=payer, feature="ai_chat_access", amount=50, status="completed")
            ids.append(AffiliateCommission.objects.create(affiliate=aff, payment=pay, amount=amount, rate_snapshot=20).pk)
        self._action(AffiliateCommission, "mark_paid_out", ids)
        aff.refresh_from_db()
        self.assertEqual(aff.wallet_balance, 0)
        wr = AffiliateWithdrawalRequest.objects.get(affiliate=aff)
        self.assertEqual((wr.status, wr.amount), ("processed", 30))
        self.assertFalse(AffiliateCommission.objects.filter(status="pending").exists())
        self.assertEqual(len(mail.outbox), 1)

    def test_activate_affiliate_emails_new_affiliate(self):
        resp = self._action(User, "activate_as_affiliate", [self.student.pk])
        self.assertTrue(AffiliateProfile.objects.filter(user=self.student).exists())
        self.assertEqual([m.to for m in mail.outbox], [[self.student.email]])
        self.assertIn(reverse("accounts:affiliate_dashboard"), mail.outbox[0].alternatives[0][0])
        self.assertTrue(any("Activated 1 new affiliate(s)" in m for m in self._messages(resp)))

    def test_affiliate_withdrawal_manual_payout(self):
        aff = AffiliateProfile.objects.create(user=self.student, wallet_balance=300)
        wr = AffiliateWithdrawalRequest.objects.create(affiliate=aff, amount=200, mpesa_number="0712345678", status="failed")
        resp = self._action(AffiliateWithdrawalRequest, "mark_processed", [wr.pk])
        wr.refresh_from_db(); aff.refresh_from_db()
        self.assertEqual(wr.status, "processed")
        self.assertEqual(aff.wallet_balance, 100)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(any("1 affiliate withdrawal(s)" in m for m in self._messages(resp)))


@override_settings(STORAGES=STATIC_STORAGES, STAFF_2FA_REQUIRED=False)  # 2FA covered in test_security
class MentorshipAdminTests(TestCase):
    def setUp(self):
        from mentorship.models import MentorProfile
        self.admin_user = User.objects.create_superuser(email="admin@example.com", password="pw-Admin-123")
        self.client.force_login(self.admin_user)
        self.mentor_user = User.objects.create_user(email="mentor@example.com", password="pw-Mentor-123")
        self.mentee = User.objects.create_user(email="mentee@example.com", password="pw-Mentee-123")
        self.mentor = MentorProfile.objects.create(user=self.mentor_user, bio="bio", whatsapp="0712345678")

    def _action(self, model, action, pks):
        url = reverse(f"admin:{model._meta.app_label}_{model._meta.model_name}_changelist")
        return self.client.post(url, {"action": action, "_selected_action": [str(pk) for pk in pks]}, follow=True)

    def test_reject_button_confirms_first_then_rejects_and_emails(self):
        url = reverse("admin:mentorship_reject_mentor", args=[self.mentor.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.mentor.refresh_from_db()
        self.assertFalse(self.mentor.is_rejected)
        self.client.post(url, {"rejection_reason": "Documents unclear"})
        self.mentor.refresh_from_db()
        self.assertTrue(self.mentor.is_rejected)
        self.assertEqual(self.mentor.rejection_reason, "Documents unclear")
        self.assertTrue(any(self.mentor_user.email in m.to for m in mail.outbox))

    def test_approve_action_emails_real_payout(self):
        from mentorship.models import MentorProfile
        self._action(MentorProfile, "approve_selected", [self.mentor.pk])
        self.mentor.refresh_from_db()
        self.assertTrue(self.mentor.is_approved)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(f"KES {self.mentor.effective_mentor_payout()}", mail.outbox[0].alternatives[0][0])

    def test_refund_of_unpaid_session_does_not_debit_mentor_and_frees_slot(self):
        from mentorship.models import MentorshipSession, TimeSlot
        self.mentor.wallet_balance = 140
        self.mentor.save()
        slot = TimeSlot.objects.create(mentor=self.mentor, date=datetime.date.today(), start_time=datetime.time(10), is_booked=True)
        s = MentorshipSession.objects.create(mentor=self.mentor, mentee=self.mentee, slot=slot, mentee_question="q", status="pending_payment")
        self._action(MentorshipSession, "mark_refunded", [s.pk])
        self.mentor.refresh_from_db(); slot.refresh_from_db()
        self.assertEqual(self.mentor.wallet_balance, 140)
        self.assertFalse(slot.is_booked)
        self.assertTrue(any(self.mentee.email in m.to for m in mail.outbox))

    def test_failed_withdrawal_can_be_settled_manually(self):
        from mentorship.models import WithdrawalRequest
        self.mentor.wallet_balance = 500
        self.mentor.save()
        wr = WithdrawalRequest.objects.create(mentor=self.mentor, amount=300, mpesa_number="0712345678", status="failed")
        self._action(WithdrawalRequest, "mark_processed", [wr.pk])
        wr.refresh_from_db(); self.mentor.refresh_from_db()
        self.assertEqual(wr.status, "processed")
        self.assertEqual(self.mentor.wallet_balance, 200)
        self.assertEqual(len(mail.outbox), 1)
