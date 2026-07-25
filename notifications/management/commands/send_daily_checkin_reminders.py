import json
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone as dj_timezone
from pywebpush import WebPushException, webpush

from notifications.models import NotificationPreference, PushSubscription


class Command(BaseCommand):
    """Sends the daily "How are you feeling today?" push to users whose local
    reminder_time has arrived. Polling-based, run every ~15 minutes via cron
    or a systemd timer — no Celery/Redis needed at 1-2 users. Revisit only if
    this stops being enough (precision/retry requirements grow)."""

    help = "Send the daily check-in reminder push notification."

    def handle(self, *args, **options):
        sent = 0
        for pref in NotificationPreference.objects.filter(reminder_enabled=True):
            tz_name = getattr(getattr(pref.user, "profile", None), "timezone", "") or "UTC"
            try:
                tz = ZoneInfo(tz_name)
            except (ZoneInfoNotFoundError, ValueError):
                tz = ZoneInfo("UTC")

            now_local = dj_timezone.now().astimezone(tz)
            today = now_local.date()

            if pref.last_sent_date == today:
                continue
            if now_local.time() < pref.reminder_time:
                continue

            subscriptions = list(PushSubscription.objects.filter(user=pref.user))
            if not subscriptions:
                continue

            payload = json.dumps(
                {
                    "title": "Recovery Pulse",
                    "body": "How are you feeling today?",
                    "url": "/home/",
                }
            )

            delivered = False
            for sub in subscriptions:
                try:
                    webpush(
                        subscription_info={
                            "endpoint": sub.endpoint,
                            "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                        },
                        data=payload,
                        vapid_private_key=settings.VAPID_PRIVATE_KEY,
                        vapid_claims={"sub": settings.VAPID_CLAIMS_EMAIL},
                    )
                    delivered = True
                except WebPushException as exc:
                    status = getattr(exc.response, "status_code", None)
                    self.stderr.write(f"Push failed for {pref.user}: {exc}")
                    if status in (404, 410):
                        # Endpoint expired/gone — stop trying it.
                        sub.delete()

            if delivered:
                pref.last_sent_date = today
                pref.save(update_fields=["last_sent_date"])
                sent += 1

        self.stdout.write(self.style.SUCCESS(f"Sent {sent} reminder(s)."))
