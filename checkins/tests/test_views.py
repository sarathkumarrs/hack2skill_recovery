from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from checkins.models import MoodCheckIn
from companion import services as companion_services
from companion.schemas import CompanionAssessment

User = get_user_model()


class CheckinCreateViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="a@example.com", email="a@example.com", password="pw12345!"
        )
        self.client.force_login(self.user)
        self.assessment = CompanionAssessment(
            message="You're doing great.", risk_level="low", suggested_action="Take a walk."
        )

    def _post(self, payload):
        return self.client.post(
            reverse("checkin_create"),
            data=payload,
            content_type="application/json",
        )

    def test_requires_login(self):
        self.client.logout()
        response = self._post({"mood": "good"})
        self.assertEqual(response.status_code, 302)  # redirected to login

    def test_missing_mood_and_transcript_is_a_400(self):
        response = self._post({})
        self.assertEqual(response.status_code, 400)

    def test_invalid_mood_is_a_400(self):
        response = self._post({"mood": "ecstatic"})
        self.assertEqual(response.status_code, 400)

    def test_tap_checkin_creates_row_and_returns_redirect_url(self):
        with mock.patch.object(
            companion_services.ai_engine, "assess_checkin", return_value=self.assessment
        ):
            response = self._post({"mood": "good"})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("redirect_url", data)

        checkin = MoodCheckIn.objects.get(user=self.user)
        self.assertEqual(checkin.mood, "good")
        self.assertEqual(checkin.input_method, MoodCheckIn.InputMethod.TAP)
        self.assertTrue(hasattr(checkin, "companion_response"))
        self.assertEqual(data["redirect_url"], reverse("checkin_response", args=[checkin.id]))

    def test_voice_checkin_without_mood_defaults_to_okay(self):
        with mock.patch.object(
            companion_services.ai_engine, "assess_checkin", return_value=self.assessment
        ):
            response = self._post({"voice_transcript": "Today was hard."})

        self.assertEqual(response.status_code, 200)
        checkin = MoodCheckIn.objects.get(user=self.user)
        self.assertEqual(checkin.mood, MoodCheckIn.Mood.OKAY)
        self.assertEqual(checkin.input_method, MoodCheckIn.InputMethod.VOICE)
        self.assertEqual(checkin.voice_transcript, "Today was hard.")

    def test_response_view_rejects_another_users_checkin(self):
        other_user = User.objects.create_user(username="c@example.com", email="c@example.com")
        with mock.patch.object(
            companion_services.ai_engine, "assess_checkin", return_value=self.assessment
        ):
            self._post({"mood": "good"})
        checkin = MoodCheckIn.objects.get(user=self.user)

        self.client.force_login(other_user)
        response = self.client.get(reverse("checkin_response", args=[checkin.id]))
        self.assertEqual(response.status_code, 404)
