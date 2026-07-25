from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from voicecalls.models import VoiceCallSession

# Same grace window services.py already gives the Daily room's own `exp` —
# a call has no legitimate reason to still be pending/active this long
# after it started; the only way it gets here is a crashed voice_bot
# process (or one that died before posting the completion webhook).
STALE_GRACE_SECONDS = 300


class Command(BaseCommand):
    """Marks any voice call session stuck in pending/active well past the
    max call duration as failed. Without this, a crashed voice_bot process
    (or an abrupt Daily transport disconnect — see README) leaves the
    session's status forever pending/active, which hangs the browser's
    post-hangup status poll (voicecalls/views.py:status) indefinitely
    instead of surfacing the "couldn't be completed" fallback. Polling-based,
    run every few minutes via cron/systemd — same shape as
    notifications.management.commands.send_daily_checkin_reminders."""

    help = "Mark stuck pending/active voice call sessions as failed."

    def handle(self, *args, **options):
        threshold = timezone.now() - timedelta(
            seconds=settings.MAX_CALL_DURATION_SECONDS + STALE_GRACE_SECONDS
        )
        stale = VoiceCallSession.objects.filter(
            status__in=[VoiceCallSession.Status.PENDING, VoiceCallSession.Status.ACTIVE],
            created_at__lt=threshold,
        )

        count = stale.update(status=VoiceCallSession.Status.FAILED, ended_at=timezone.now())

        self.stdout.write(self.style.SUCCESS(f"Marked {count} stale voice call session(s) as failed."))
