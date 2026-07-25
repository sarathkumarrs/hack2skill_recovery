from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from checkins.models import MoodCheckIn
from checkins.services import create_checkin
from companion import services
from companion.ai_engine import AIEngineError
from companion.schemas import CompanionAssessment

User = get_user_model()


class CreateCompanionResponseTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="a@example.com", email="a@example.com")

    def _checkin(self, mood=MoodCheckIn.Mood.GOOD, voice_transcript=None):
        return create_checkin(
            user=self.user,
            mood=mood,
            input_method=MoodCheckIn.InputMethod.VOICE if voice_transcript else MoodCheckIn.InputMethod.TAP,
            voice_transcript=voice_transcript,
        )

    def test_success_branch_persists_llm_output(self):
        checkin = self._checkin()
        assessment = CompanionAssessment(
            message="Nice work checking in.", risk_level="low", suggested_action="Take a walk."
        )
        with mock.patch.object(services.ai_engine, "assess_checkin", return_value=assessment):
            response = services.create_companion_response(checkin)

        self.assertEqual(response.message, assessment.message)
        self.assertEqual(response.suggested_action, assessment.suggested_action)
        self.assertEqual(response.llm_risk_level, "low")
        self.assertEqual(response.risk_level, "low")
        self.assertFalse(response.crisis_flag)
        self.assertFalse(response.error_occurred)
        self.assertEqual(response.raw_response_json, assessment.model_dump())

    def test_failure_branch_falls_back_to_safety_floor(self):
        checkin = self._checkin(mood=MoodCheckIn.Mood.CRAVING)
        with mock.patch.object(
            services.ai_engine, "assess_checkin", side_effect=AIEngineError("boom")
        ):
            response = services.create_companion_response(checkin)

        self.assertTrue(response.error_occurred)
        self.assertEqual(response.error_detail, "boom")
        self.assertEqual(response.llm_risk_level, "")
        # craving mood floor + LLM-unavailable fallback both push to at least medium
        self.assertEqual(response.risk_level, "medium")
        self.assertEqual(response.suggested_action, services.FALLBACK_SUGGESTED_ACTION)

    def test_crisis_keyword_overrides_even_on_success_branch(self):
        checkin = self._checkin(
            mood=MoodCheckIn.Mood.OKAY, voice_transcript="I want to give up on everything."
        )
        assessment = CompanionAssessment(
            message="Sounds tough.", risk_level="low", suggested_action="Take a walk."
        )
        with mock.patch.object(services.ai_engine, "assess_checkin", return_value=assessment):
            response = services.create_companion_response(checkin)

        self.assertEqual(response.risk_level, "high")
        self.assertTrue(response.crisis_flag)
        # The LLM's own (pre-floor) assessment is still retained for audit.
        self.assertEqual(response.llm_risk_level, "low")

    def test_mood_history_passed_to_ai_engine_is_oldest_to_newest(self):
        self._checkin(mood=MoodCheckIn.Mood.GOOD)
        self._checkin(mood=MoodCheckIn.Mood.OKAY)
        latest = self._checkin(mood=MoodCheckIn.Mood.STRUGGLING)

        assessment = CompanionAssessment(
            message="Hang in there.", risk_level="medium", suggested_action="Breathe."
        )
        with mock.patch.object(
            services.ai_engine, "assess_checkin", return_value=assessment
        ) as mocked:
            services.create_companion_response(latest)

        _, kwargs = mocked.call_args
        self.assertEqual(kwargs["mood_history"], ["good", "okay"])
