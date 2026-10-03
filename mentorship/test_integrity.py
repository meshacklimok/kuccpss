"""
Concurrency/integrity tests for mentor wallets: one in-flight payout per mentor,
idempotent session confirmation, and debits that never go below zero.
"""
import time
import uuid
from datetime import date, time as dtime, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from analytics.models import AuditLog
from mentorship.models import MentorProfile, MentorshipSession, TimeSlot, WithdrawalRequest
from mentorship.views import _confirm_session_after_payment

User = get_user_model()


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class MentorWalletIntegrityTests(TestCase):
    def setUp(self):
        self.mentor_user = User.objects.create_user(email="mentor@example.com", password="pass1234")
        self.mentor = MentorProfile.objects.create(
            user=self.mentor_user, bio="Mentor", whatsapp="+254712345678",
            is_approved=True, wallet_balance=1000,
        )
        mentee = User.objects.create_user(email="mentee@example.com", password="pass1234")
        slot = TimeSlot.objects.create(mentor=self.mentor, date=date.today() + timedelta(days=1), start_time=dtime(14, 0))
        self.session = MentorshipSession.objects.create(
            token=uuid.uuid4(), mentor=self.mentor, mentee=mentee, slot=slot,
            mentee_question="Q", amount=100, mentor_payout=70, status="pending_payment",
        )

    def _login_recent(self):
        self.client.force_login(self.mentor_user)
        s = self.client.session
        s["_auth_verified_at"] = time.time()
        s.save()

    def test_only_one_pending_withdrawal_per_mentor(self):
        WithdrawalRequest.objects.create(mentor=self.mentor, amount=100, mpesa_number="0712", status="pending")
        with self.assertRaises(IntegrityError), transaction.atomic():
            WithdrawalRequest.objects.create(mentor=self.mentor, amount=100, mpesa_number="0712", status="pending")
        # Non-pending rows are unrestricted.
        WithdrawalRequest.objects.create(mentor=self.mentor, amount=100, mpesa_number="0712", status="failed")

    @patch("mentorship.views._maybe_auto_pay_mentor")
    def test_confirmation_is_idempotent(self, _auto_pay):
        _confirm_session_after_payment(self.session, source="test-1")
        _confirm_session_after_payment(self.session, source="test-2")
        self.mentor.refresh_from_db()
        self.assertEqual(self.mentor.wallet_balance, 1070)
        self.assertEqual(self.mentor.total_earned, 70)
        self.assertEqual(AuditLog.objects.filter(action="mentor.wallet_credited").count(), 1)

    @patch("payments.services.send_mentor_payout")
    def test_withdrawal_blocked_while_one_is_pending(self, payout):
        WithdrawalRequest.objects.create(mentor=self.mentor, amount=200, mpesa_number="0712", status="pending")
        self._login_recent()
        self.client.post(reverse("mentorship:request_withdrawal"),
                         {"amount": 500, "mpesa_number": "+254712345678"})
        payout.assert_not_called()
        self.mentor.refresh_from_db()
        self.assertEqual(self.mentor.wallet_balance, 1000)

    @patch("payments.services.send_mentor_payout")
    def test_successful_withdrawal_debits_once(self, payout):
        self._login_recent()
        self.client.post(reverse("mentorship:request_withdrawal"),
                         {"amount": 500, "mpesa_number": "+254712345678"})
        payout.assert_called_once()
        self.mentor.refresh_from_db()
        self.assertEqual(self.mentor.wallet_balance, 500)
        self.assertEqual(WithdrawalRequest.objects.get().status, "processed")

    @patch("payments.services.send_mentor_payout", side_effect=RuntimeError("B2C down"))
    def test_failed_payout_leaves_wallet_untouched(self, _payout):
        self._login_recent()
        self.client.post(reverse("mentorship:request_withdrawal"),
                         {"amount": 500, "mpesa_number": "+254712345678"})
        self.mentor.refresh_from_db()
        self.assertEqual(self.mentor.wallet_balance, 1000)
        self.assertEqual(WithdrawalRequest.objects.get().status, "failed")
