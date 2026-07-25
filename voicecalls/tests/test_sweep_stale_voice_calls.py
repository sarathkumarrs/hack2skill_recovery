from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from voicecalls.models import VoiceCallSession

User = get_user_model()


@override_settings(MAX_CALL_DURATION_SECONDS=600)
class SweepStaleVoiceCallsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="a@example.com", email="a@example.com")

    def _make_session(self, status, created_at):
        session = VoiceCallSession.objects.create(
            user=self.user, room_name="rp-test", room_url="https://x.daily.co/rp-test", status=status
        )
        VoiceCallSession.objects.filter(pk=session.pk).update(created_at=created_at)
        session.refresh_from_db()
        return session

    def _run_command(self):
        out = StringIO()
        call_command("sweep_stale_voice_calls", stdout=out)
        return out.getvalue()

    def test_old_active_session_is_marked_failed(self):
        stale_at = timezone.now() - timedelta(seconds=600 + 300 + 1)
        session = self._make_session(VoiceCallSession.Status.ACTIVE, stale_at)

        self._run_command()

        session.refresh_from_db()
        self.assertEqual(session.status, VoiceCallSession.Status.FAILED)
        self.assertIsNotNone(session.ended_at)

    def test_old_pending_session_is_marked_failed(self):
        stale_at = timezone.now() - timedelta(seconds=600 + 300 + 1)
        session = self._make_session(VoiceCallSession.Status.PENDING, stale_at)

        self._run_command()

        session.refresh_from_db()
        self.assertEqual(session.status, VoiceCallSession.Status.FAILED)

    def test_recent_active_session_is_left_alone(self):
        recent = timezone.now() - timedelta(seconds=30)
        session = self._make_session(VoiceCallSession.Status.ACTIVE, recent)

        self._run_command()

        session.refresh_from_db()
        self.assertEqual(session.status, VoiceCallSession.Status.ACTIVE)

    def test_old_completed_session_is_left_alone(self):
        stale_at = timezone.now() - timedelta(seconds=600 + 300 + 1)
        session = self._make_session(VoiceCallSession.Status.COMPLETED, stale_at)

        self._run_command()

        session.refresh_from_db()
        self.assertEqual(session.status, VoiceCallSession.Status.COMPLETED)

    def test_reports_count_swept(self):
        stale_at = timezone.now() - timedelta(seconds=600 + 300 + 1)
        self._make_session(VoiceCallSession.Status.ACTIVE, stale_at)
        self._make_session(VoiceCallSession.Status.PENDING, stale_at)

        output = self._run_command()

        self.assertIn("Marked 2 stale voice call session(s) as failed.", output)
