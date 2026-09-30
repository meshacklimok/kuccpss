"""
Remove a staff member's 2FA device so they re-enrol at next login
(lost / replaced phone, or the only superuser locked out).

  python manage.py reset_staff_2fa someone@careernext.co.ke
"""
from django.core.management.base import BaseCommand, CommandError

from accounts.models import StaffTOTPDevice


class Command(BaseCommand):
    help = "Delete a staff user's 2FA device so they must set it up again."

    def add_arguments(self, parser):
        parser.add_argument("email")

    def handle(self, *args, **options):
        deleted, _ = StaffTOTPDevice.objects.filter(user__email__iexact=options["email"]).delete()
        if not deleted:
            raise CommandError(f"No 2FA device found for {options['email']}")
        self.stdout.write(self.style.SUCCESS(
            f"2FA reset for {options['email']} — they will set it up again at next login."
        ))
