"""
End-to-end booking flow: book → pay → confirm → calendar (.ics / Google link) →
cancel → rebook. Covers the slot lifecycle and calendar output.
"""
import uuid
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from mentorship.calendar_utils import generate_ics, google_calendar_url
from mentorship.models import MentorProfile, MentorshipSession, TimeSlot

User = get_user_model()


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class BookingFlowTests(TestCase):
    def setUp(self):
        cache.clear()  # the per-IP rate limiter would otherwise carry over between tests
        mentor_user = User.objects.create_user(email="mentor@example.com", password="pass1234")
        self.mentor = MentorProfile.objects.create(
            user=mentor_user, bio="Mentor", whatsapp="+254712345678", is_approved=True,
        )
        self.mentee = User.objects.create_user(email="mentee@example.com", password="pass1234")
        self.slot = TimeSlot.objects.create(
            mentor=self.mentor, date=date.today() + timedelta(days=2), start_time="14:00",
        )

    def _book(self, user, question="What is campus life like?"):
        self.client.force_login(user)
        return self.client.post(
            reverse("mentorship:book_session", args=[self.mentor.pk]),
            {"slot": self.slot.pk, "mentee_question": question, "mentee_phone": "0712345678"},
        )

    def _confirm(self, session):
        from mentorship.views import _confirm_session_after_payment
        _confirm_session_after_payment(session, source="test")
        session.refresh_from_db()

    def test_cancelled_slot_can_be_rebooked(self):
        self._book(self.mentee)
        session = MentorshipSession.objects.get(slot=self.slot)
        self._confirm(session)
        self.client.post(reverse("mentorship:cancel_session", args=[session.token]), {"reason": "Clash with exam"})
        session.refresh_from_db()
        self.assertEqual(session.status, "cancelled")

        other = User.objects.create_user(email="other@example.com", password="pass1234")
        resp = self._book(other)
        self.assertEqual(resp.status_code, 302)
        new = MentorshipSession.objects.get(mentee=other)
        self.assertEqual(new.slot_id, self.slot.pk)

    def test_abandoned_checkout_releases_slot(self):
        from mentorship.tasks import release_abandoned_bookings
        self._book(self.mentee)
        session = MentorshipSession.objects.get(slot=self.slot)
        MentorshipSession.objects.filter(pk=session.pk).update(
            created_at=session.created_at - timedelta(minutes=31)
        )
        self.assertEqual(release_abandoned_bookings(), 1)
        session.refresh_from_db()
        self.slot.refresh_from_db()
        self.assertEqual(session.status, "cancelled")
        self.assertFalse(self.slot.is_booked)

    def test_booked_slot_cannot_be_double_booked(self):
        self._book(self.mentee)
        other = User.objects.create_user(email="other@example.com", password="pass1234")
        resp = self._book(other)
        self.assertEqual(resp.status_code, 200)  # form re-rendered, slot no longer offered
        self.assertFalse(MentorshipSession.objects.filter(mentee=other).exists())

    def test_confirmation_email_has_calendar_invite_and_link(self):
        self._book(self.mentee)
        session = MentorshipSession.objects.get(slot=self.slot)
        mail.outbox.clear()
        self._confirm(session)
        mentee_mail = next(m for m in mail.outbox if m.to == ["mentee@example.com"])
        names = [a[0] for a in mentee_mail.attachments]
        self.assertIn(f"session_{session.token}.ics", names)
        self.assertIn("calendar.google.com", mentee_mail.alternatives[0][0])

    def test_ics_escapes_user_text(self):
        self._book(self.mentee, question="Fees; housing, etc\r\nBEGIN:VALARM\r\nTRIGGER:-PT1M")
        session = MentorshipSession.objects.get(slot=self.slot)
        ics = generate_ics(session)
        self.assertNotIn("\r\nBEGIN:VALARM\r\nTRIGGER:-PT1M", ics)
        self.assertIn(r"Fees\; housing\, etc", ics)
        self.assertEqual(ics.split("\r\n").count("BEGIN:VALARM"), 2)  # only our two real alarms
        for line in ics.split("\r\n"):
            self.assertLessEqual(len(line.encode("utf-8")), 75)

    def test_ics_times_are_nairobi_converted_to_utc(self):
        self._book(self.mentee)
        session = MentorshipSession.objects.get(slot=self.slot)
        ics = generate_ics(session)
        d = self.slot.date.strftime("%Y%m%d")
        self.assertIn(f"DTSTART:{d}T110000Z", ics)  # 14:00 EAT = 11:00 UTC
        self.assertIn(f"DTEND:{d}T111500Z", ics)
        self.assertIn(f"{d}T110000Z/{d}T111500Z", google_calendar_url(session))

    def test_download_ics(self):
        self._book(self.mentee)
        session = MentorshipSession.objects.get(slot=self.slot)
        self._confirm(session)
        resp = self.client.get(reverse("mentorship:download_ics", args=[session.token]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "text/calendar; charset=utf-8")
        self.assertIn(b"METHOD:PUBLISH", resp.content)

    def test_cancellation_emails_carry_calendar_cancel(self):
        self._book(self.mentee)
        session = MentorshipSession.objects.get(slot=self.slot)
        self._confirm(session)
        mail.outbox.clear()
        self.client.post(reverse("mentorship:cancel_session", args=[session.token]), {"reason": "Clash with exam"})
        mentee_mail = next(m for m in mail.outbox if m.to == ["mentee@example.com"])
        ics = mentee_mail.attachments[0][1]
        self.assertIn("METHOD:CANCEL", ics)
        self.assertIn(f"UID:{session.token}@careernext.co.ke", ics)
        self.assertIn("STATUS:CANCELLED", ics)

    def test_auto_completed_session_asks_mentee_to_rate(self):
        from django.utils import timezone
        from mentorship.tasks import complete_expired_sessions
        self._book(self.mentee)
        session = MentorshipSession.objects.get(slot=self.slot)
        self._confirm(session)
        past = timezone.localtime() - timedelta(hours=2)
        TimeSlot.objects.filter(pk=self.slot.pk).update(date=past.date(), start_time=past.time())
        mail.outbox.clear()
        self.assertEqual(complete_expired_sessions(), 1)
        self.assertTrue(any("rate" in m.subject.lower() or "How was" in m.subject for m in mail.outbox))

    def _age_booking(self, minutes):
        self._book(self.mentee)
        session = MentorshipSession.objects.get(slot=self.slot)
        MentorshipSession.objects.filter(pk=session.pk).update(
            created_at=session.created_at - timedelta(minutes=minutes), payment_ref="CHK123",
        )
        return session

    def test_abandoned_release_waits_while_mpesa_processing(self):
        from unittest.mock import patch
        from mentorship.tasks import release_abandoned_bookings
        session = self._age_booking(40)
        with patch("payments.services.fetch_intasend_status", return_value="PENDING"):
            self.assertEqual(release_abandoned_bookings(), 0)
        session.refresh_from_db()
        self.assertEqual(session.status, "pending_payment")

    def test_abandoned_release_confirms_if_actually_paid(self):
        from unittest.mock import patch
        from mentorship.tasks import release_abandoned_bookings
        session = self._age_booking(40)
        with patch("payments.services.fetch_intasend_status", return_value="COMPLETE"):
            self.assertEqual(release_abandoned_bookings(), 0)
        session.refresh_from_db()
        self.assertEqual(session.status, "confirmed")

    def _submit_code(self, session, code):
        self.client.force_login(self.mentee)
        return self.client.post(reverse("mentorship:verify_payment_manual", args=[session.token]), {"mpesa_code": code})

    def test_manual_code_rejects_non_mpesa_text(self):
        session = self._age_booking(5)
        self._submit_code(session, "hello")
        session.refresh_from_db()
        self.assertEqual(session.status, "pending_payment")
        self.assertEqual(session.manual_payment_ref, "")

    def test_manual_code_stores_intasend_ref_when_paid(self):
        from unittest.mock import patch
        session = self._age_booking(5)
        with patch("payments.services.fetch_intasend_invoice",
                   return_value={"state": "COMPLETE", "mpesa_ref": "TGH4ABC123"}):
            self._submit_code(session, "Invoice R7KQ2PX9WZ paid")
        session.refresh_from_db()
        self.assertEqual(session.status, "confirmed")
        self.assertEqual(session.manual_payment_ref, "TGH4ABC123")

    def test_manual_code_extracted_from_pasted_sms(self):
        from unittest.mock import patch
        session = self._age_booking(5)
        with patch("payments.services.fetch_intasend_invoice", return_value={"state": "PENDING", "mpesa_ref": ""}):
            self._submit_code(session, "tgh4abc123 Confirmed. Ksh500.00 sent to IntaSend")
        session.refresh_from_db()
        self.assertEqual(session.status, "pending_manual_verification")
        self.assertEqual(session.manual_payment_ref, "TGH4ABC123")

    def test_expired_checkout_redirects_to_booking(self):
        self._book(self.mentee)
        session = MentorshipSession.objects.get(slot=self.slot)
        MentorshipSession.objects.filter(pk=session.pk).update(status="cancelled")
        resp = self.client.get(reverse("mentorship:checkout", args=[session.token]))
        self.assertRedirects(resp, reverse("mentorship:book_session", args=[self.mentor.pk]))

    def test_mentor_cannot_complete_before_start(self):
        self._book(self.mentee)
        session = MentorshipSession.objects.get(slot=self.slot)
        self._confirm(session)
        self.client.force_login(self.mentor.user)
        self.client.post(reverse("mentorship:complete_session", args=[session.token]))
        session.refresh_from_db()
        self.assertEqual(session.status, "confirmed")

    def test_slot_starting_too_soon_not_offered(self):
        from django.utils import timezone
        from mentorship.forms import BookingForm
        soon = timezone.localtime() + timedelta(minutes=10)
        TimeSlot.objects.filter(pk=self.slot.pk).update(date=soon.date(), start_time=soon.time())
        self.assertFalse(BookingForm(self.mentor).fields["slot"].queryset.exists())


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class MoneyLoopholeTests(TestCase):
    """Wallet reversal after payout, single confirmation email, admin completion,
    and M-Pesa payments that land after a booking was released."""

    def setUp(self):
        cache.clear()
        mentor_user = User.objects.create_user(email="mentor@example.com", password="pass1234")
        self.mentor = MentorProfile.objects.create(
            user=mentor_user, bio="Mentor", whatsapp="+254712345678", is_approved=True,
        )
        self.mentee = User.objects.create_user(email="mentee@example.com", password="pass1234")
        self.slot = TimeSlot.objects.create(
            mentor=self.mentor, date=date.today() + timedelta(days=2), start_time="14:00",
        )

    _book = BookingFlowTests._book
    _confirm = BookingFlowTests._confirm

    def _booked_with_payment(self):
        from payments.models import Payment
        self._book(self.mentee)
        session = MentorshipSession.objects.get(slot=self.slot)
        Payment.objects.create(
            user=self.mentee, feature="mentorship_booking", amount=session.amount,
            phone_number="0712345678", status="pending", mentorship_session=session,
        )
        return session

    def test_cancel_after_payout_records_debt_and_recovers_it(self):
        self._book(self.mentee)
        session = MentorshipSession.objects.get(slot=self.slot)
        self._confirm(session)
        payout = session.mentor_payout
        MentorProfile.objects.filter(pk=self.mentor.pk).update(wallet_balance=0)  # already paid out

        self.client.force_login(self.mentor.user)
        self.client.post(reverse("mentorship:cancel_session", args=[session.token]), {"reason": "Emergency"})
        self.mentor.refresh_from_db()
        self.assertEqual(self.mentor.wallet_balance, 0)
        self.assertEqual(self.mentor.payout_debt, payout)
        self.assertEqual(self.mentor.total_earned, 0)

        # The next paid session repays the debt before anything reaches the wallet.
        self.slot.refresh_from_db()
        self._book(self.mentee)
        new = MentorshipSession.objects.get(slot=self.slot, status="pending_payment")
        self._confirm(new)
        self.mentor.refresh_from_db()
        self.assertEqual(self.mentor.payout_debt, 0)
        self.assertEqual(self.mentor.wallet_balance, 0)
        self.assertEqual(self.mentor.total_earned, payout)

    def test_confirmation_emails_sent_once_despite_status_poll(self):
        self._book(self.mentee)
        session = MentorshipSession.objects.get(slot=self.slot)
        mail.outbox.clear()
        self._confirm(session)
        sent = len(mail.outbox)
        self.assertGreater(sent, 0)
        MentorshipSession.objects.filter(pk=session.pk).update(confirmation_sent=False)
        from mentorship.views import _send_confirmation_once
        # A concurrent sender already claimed the flag → the poll must not send again.
        MentorshipSession.objects.filter(pk=session.pk).update(confirmation_sent=True)
        self.client.get(reverse("mentorship:session_status", args=[session.token]))
        _send_confirmation_once(session)
        self.assertEqual(len(mail.outbox), sent)

    def test_failed_confirmation_send_is_retried(self):
        from unittest.mock import patch
        from mentorship.views import _send_confirmation_once
        self._book(self.mentee)
        session = MentorshipSession.objects.get(slot=self.slot)
        with patch("mentorship.views._send_booking_confirmation", return_value=False):
            self._confirm(session)
        session.refresh_from_db()
        self.assertFalse(session.confirmation_sent)
        _send_confirmation_once(session)
        session.refresh_from_db()
        self.assertTrue(session.confirmation_sent)

    def test_admin_mark_completed_sends_rating_request(self):
        from django.contrib.admin.sites import site
        self._book(self.mentee)
        session = MentorshipSession.objects.get(slot=self.slot)
        self._confirm(session)
        model_admin = site._registry[MentorshipSession]
        model_admin.message_user = lambda *a, **k: None
        mail.outbox.clear()
        model_admin.mark_completed(None, MentorshipSession.objects.filter(pk=session.pk))
        session.refresh_from_db()
        self.assertEqual(session.status, "completed")
        self.assertTrue(any(m.to == ["mentee@example.com"] for m in mail.outbox))

    def _release(self, session):
        from mentorship.tasks import release_abandoned_bookings
        MentorshipSession.objects.filter(pk=session.pk).update(created_at=session.created_at - timedelta(minutes=31))
        self.assertEqual(release_abandoned_bookings(), 1)
        session.refresh_from_db()
        self.assertEqual(session.status, "cancelled")

    def test_late_payment_reclaims_free_slot(self):
        from mentorship.views import handle_paid_session
        session = self._booked_with_payment()
        self._release(session)
        handle_paid_session(session, source="test")
        session.refresh_from_db()
        self.slot.refresh_from_db()
        self.assertEqual(session.status, "confirmed")
        self.assertTrue(self.slot.is_booked)

    def test_late_payment_on_taken_slot_flags_refund_once(self):
        from payments.models import Payment
        from mentorship.views import handle_paid_session
        session = self._booked_with_payment()
        self._release(session)
        other = User.objects.create_user(email="other@example.com", password="pass1234")
        self._book(other)  # someone else takes the freed slot
        mail.outbox.clear()
        handle_paid_session(session, source="test")
        handle_paid_session(session, source="test")  # webhook retry
        session.refresh_from_db()
        self.assertEqual(session.status, "cancelled")
        self.assertEqual(Payment.objects.get(mentorship_session=session).status, "completed")
        self.assertEqual(sum(m.to == ["mentee@example.com"] for m in mail.outbox), 1)
        self.assertEqual(len(mail.outbox), 2)  # mentee + admin, once
        self.assertTrue(MentorshipSession.objects.get(mentee=other).status == "pending_payment")

    def test_payment_after_user_cancel_is_ignored(self):
        from mentorship.views import handle_paid_session
        session = self._booked_with_payment()
        self._confirm(session)
        self.client.post(reverse("mentorship:cancel_session", args=[session.token]), {"reason": "Clash"})
        session.refresh_from_db()
        mail.outbox.clear()
        handle_paid_session(session, source="test")  # duplicate webhook
        session.refresh_from_db()
        self.assertEqual(session.status, "cancelled")
        self.assertEqual(len(mail.outbox), 0)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AutoRefundTests(TestCase):
    """Refunds go back through IntaSend automatically, exactly once."""

    setUp = MoneyLoopholeTests.setUp
    _book = BookingFlowTests._book
    _confirm = BookingFlowTests._confirm
    _release = MoneyLoopholeTests._release

    def _paid_session(self):
        from payments.models import Payment
        self._book(self.mentee)
        session = MentorshipSession.objects.get(slot=self.slot)
        MentorshipSession.objects.filter(pk=session.pk).update(payment_ref="INV123")
        Payment.objects.create(
            user=self.mentee, feature="mentorship_booking", amount=session.amount,
            phone_number="0712345678", status="pending", mentorship_session=session,
        )
        session.refresh_from_db()
        return session

    def test_mentee_cancel_refunds_via_intasend(self):
        from unittest.mock import patch
        from payments.models import Payment
        session = self._paid_session()
        self._confirm(session)
        mail.outbox.clear()
        with patch("payments.services.request_intasend_refund", return_value="CB42") as refund:
            self.client.post(reverse("mentorship:cancel_session", args=[session.token]), {"reason": "Clash"})
        refund.assert_called_once()
        self.assertEqual(refund.call_args[0][:2], ("INV123", session.amount))
        session.refresh_from_db()
        self.assertEqual(session.status, "refunded")
        self.assertEqual(session.refund_ref, "CB42")
        self.assertEqual(Payment.objects.get(mentorship_session=session).status, "refunded")
        self.mentor.refresh_from_db()
        self.assertEqual(self.mentor.wallet_balance, 0)  # credit reversed exactly once
        mentee_mail = next(m for m in mail.outbox if m.to == ["mentee@example.com"])
        self.assertIn("refund of KES", mentee_mail.body)

    def test_refund_is_never_issued_twice(self):
        from unittest.mock import patch
        from mentorship.views import refund_session
        session = self._paid_session()
        self._confirm(session)
        with patch("payments.services.request_intasend_refund", return_value="CB1") as refund:
            self.assertTrue(refund_session(session, "test", "test"))
            again = MentorshipSession.objects.get(pk=session.pk)
            self.assertFalse(refund_session(again, "test", "test"))
        refund.assert_called_once()

    def test_failed_refund_alerts_admin_and_can_be_retried(self):
        from unittest.mock import patch
        from django.contrib.admin.sites import site
        session = self._paid_session()
        self._confirm(session)
        mail.outbox.clear()
        with patch("payments.services.request_intasend_refund", side_effect=RuntimeError("IntaSend down")):
            self.client.post(reverse("mentorship:cancel_session", args=[session.token]), {"reason": "Clash"})
        session.refresh_from_db()
        self.assertEqual(session.status, "cancelled")
        self.assertIn("IntaSend down", session.refund_error)
        self.assertIsNone(session.refund_requested_at)
        self.assertTrue(any("Refund" in m.subject and "ACTION" in m.subject for m in mail.outbox))

        model_admin = site._registry[MentorshipSession]
        model_admin.message_user = lambda *a, **k: None
        with patch("payments.services.request_intasend_refund", return_value="CB7"):
            model_admin.refund_via_intasend(None, MentorshipSession.objects.filter(pk=session.pk))
        session.refresh_from_db()
        self.assertEqual(session.status, "refunded")
        self.assertEqual(session.refund_ref, "CB7")

    def test_late_payment_on_taken_slot_refunds_automatically(self):
        from unittest.mock import patch
        from mentorship.views import handle_paid_session
        session = self._paid_session()
        with patch("payments.services.fetch_intasend_status", return_value="FAILED"):
            self._release(session)
        other = User.objects.create_user(email="other@example.com", password="pass1234")
        self._book(other)
        mail.outbox.clear()
        with patch("payments.services.request_intasend_refund", return_value="CB9") as refund:
            handle_paid_session(session, source="test")
            handle_paid_session(MentorshipSession.objects.get(pk=session.pk), source="test")  # retry
        refund.assert_called_once()
        session.refresh_from_db()
        self.assertEqual(session.status, "refunded")
        self.assertEqual([m.to for m in mail.outbox], [["mentee@example.com"]])  # no admin action needed
