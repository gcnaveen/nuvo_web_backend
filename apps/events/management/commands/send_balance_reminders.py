# apps/events/management/commands/send_balance_reminders.py
"""
Management command: send balance payment reminders.

Run daily (cron / scheduled Lambda):
    python manage.py send_balance_reminders

Finds all events where:
  - advance_type = HALF
  - payment_status = advance (50% paid)
  - balance_due_date is today (within 24 hours)
  - balance_reminder_sent = False

Sends a reminder email to the client and marks reminder_sent = True.
"""
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings


class Command(BaseCommand):
    help = "Send balance payment reminder emails for events due within 24 hours"

    def handle(self, *args, **options):
        from apps.events.models import Event

        now       = datetime.utcnow()
        window_start = now
        window_end   = now + timedelta(hours=24)

        # Find events with unpaid balance due within the next 24 hours
        events = Event.objects(
            payment__advance_type="HALF",
            payment__payment_status="advance",
            payment__balance_reminder_sent=False,
            payment__balance_due_date__gte=window_start,
            payment__balance_due_date__lte=window_end,
        )

        sent = 0
        for event in events:
            try:
                client_email = self._get_client_email(event)
                client_name  = self._get_client_name(event)

                if not client_email:
                    self.stdout.write(f"  Skipping event {event.id} — no client email")
                    continue

                balance = max(0, (event.payment.total_amount or 0) - (event.payment.paid_amount or 0))
                due_str = event.payment.balance_due_date.strftime("%d %b %Y") if event.payment.balance_due_date else "soon"

                send_mail(
                    subject=f"Balance Payment Reminder — {event.event_name}",
                    message=(
                        f"Dear {client_name or 'Customer'},\n\n"
                        f"This is a reminder that the remaining balance of ₹{balance:,.2f} "
                        f"for your event '{event.event_name}' is due by {due_str}.\n\n"
                        f"Please complete the payment to avoid any disruption to your event.\n\n"
                        f"Event Date: {event.event_start_datetime.strftime('%d %b %Y') if event.event_start_datetime else '—'}\n"
                        f"Amount Due: ₹{balance:,.2f}\n\n"
                        f"To pay, open the Nuvo Hosting app and go to your event details.\n\n"
                        f"Regards,\nNuvo Hosting Team"
                    ),
                    from_email=settings.EMAIL_HOST_USER,
                    recipient_list=[client_email],
                    fail_silently=False,
                )

                event.payment.balance_reminder_sent = True
                event.save()
                sent += 1
                self.stdout.write(f"  Reminder sent → {client_email} (event: {event.event_name})")

            except Exception as e:
                self.stderr.write(f"  Failed for event {event.id}: {e}")

        self.stdout.write(self.style.SUCCESS(f"Done — {sent} reminder(s) sent."))

    def _get_client_email(self, event) -> str:
        try:
            return event.client.user.email or ""
        except Exception:
            return ""

    def _get_client_name(self, event) -> str:
        try:
            return event.client.full_name or ""
        except Exception:
            return ""
