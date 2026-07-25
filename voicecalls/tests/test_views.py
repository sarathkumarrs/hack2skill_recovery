import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from checkins.models import MoodCheckIn
from voicecalls.models import VoiceCallSession

User = get_user_model()


@override_settings(VOICE_SERVICE_SHARED_SECRET="test-secret")
class WebhookCompleteTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="a@example.com", email="a@example.com")
        self.session = VoiceCallSession.objects.create(
            user=self.user, room_name="rp-test", room_url="https://x.daily.co/rp-test"
        )

    def _post(self, secret, payload):
        return self.client.post(
            reverse("voicecall_webhook_complete"),
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_VOICE_SERVICE_SECRET=secret,
        )

    def test_missing_secret_is_403(self):
        response = self.client.post(
            reverse("voicecall_webhook_complete"),
            data=json.dumps({"session_id": self.session.id, "transcript": "hi"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_wrong_secret_is_403(self):
        response = self._post("wrong", {"session_id": self.session.id, "transcript": "hi"})
        self.assertEqual(response.status_code, 403)

    @mock.patch("voicecalls.views.complete_call")
    def test_correct_secret_completes_call(self, mock_complete):
        mock_checkin = mock.Mock(id=42)
        mock_complete.return_value = mock_checkin

        response = self._post(
            "test-secret",
            {"session_id": self.session.id, "transcript": "hi", "crisis_detected_live": False},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "checkin_id": 42})


class StartCallViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="a@example.com", email="a@example.com", password="pw12345!"
        )
        self.client.force_login(self.user)

    def test_requires_login(self):
        self.client.logout()
        response = self.client.post(reverse("voicecall_start"))
        self.assertEqual(response.status_code, 302)

    @mock.patch("voicecalls.views.start_call")
    def test_success_returns_session_info(self, mock_start):
        session = mock.Mock(id=1, room_url="https://x.daily.co/rp-1")
        mock_start.return_value = (session, "user-token")

        response = self.client.post(reverse("voicecall_start"))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["session_id"], 1)
        self.assertEqual(data["user_token"], "user-token")

    @mock.patch("voicecalls.views.start_call")
    def test_already_active_is_409(self, mock_start):
        from voicecalls.services import VoiceCallAlreadyActiveError

        mock_start.side_effect = VoiceCallAlreadyActiveError("busy")

        response = self.client.post(reverse("voicecall_start"))
        self.assertEqual(response.status_code, 409)


class StatusViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="a@example.com", email="a@example.com", password="pw12345!"
        )
        self.client.force_login(self.user)

    def test_completed_session_returns_redirect_url(self):
        checkin = MoodCheckIn.objects.create(
            user=self.user,
            mood="okay",
            input_method=MoodCheckIn.InputMethod.CALL,
            local_date="2026-01-01",
        )
        session = VoiceCallSession.objects.create(
            user=self.user,
            room_name="rp-test",
            room_url="https://x.daily.co/rp-test",
            status=VoiceCallSession.Status.COMPLETED,
            checkin=checkin,
        )

        response = self.client.get(reverse("voicecall_status", args=[session.id]))

        data = response.json()
        self.assertEqual(data["status"], "completed")
        self.assertEqual(data["redirect_url"], reverse("checkin_response", args=[checkin.id]))

    def test_other_users_session_is_404(self):
        other = User.objects.create_user(username="c@example.com", email="c@example.com")
        session = VoiceCallSession.objects.create(
            user=other, room_name="rp-test", room_url="https://x.daily.co/rp-test"
        )

        response = self.client.get(reverse("voicecall_status", args=[session.id]))
        self.assertEqual(response.status_code, 404)
