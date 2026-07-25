from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from checkins.models import MoodCheckIn
from companion.ai_engine import AIEngineError
from voicecalls import services
from voicecalls.models import VoiceCallSession

User = get_user_model()


def _mock_response(status_code=200, json_data=None, text=""):
    resp = mock.Mock()
    resp.status_code = status_code
    resp.ok = 200 <= status_code < 300
    resp.text = text
    resp.json.return_value = json_data or {}
    resp.raise_for_status = mock.Mock()
    if not resp.ok:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return resp


def _daily_and_bot_side_effect(*, start_bot_ok=True):
    """Returns a requests.post side_effect covering, in order: room create,
    user token, bot token, start-bot call."""
    responses = [
        _mock_response(200, {"name": "rp-test123", "url": "https://x.daily.co/rp-test123"}),
        _mock_response(200, {"token": "user-token"}),
        _mock_response(200, {"token": "bot-token"}),
    ]
    if start_bot_ok:
        responses.append(_mock_response(200, {"status": "started"}))
    else:
        responses.append(_mock_response(503, text="voice_bot unavailable"))
    return responses


@override_settings(
    DAILY_API_KEY="test-daily-key",
    VOICE_SERVICE_URL="http://localhost:7860",
    VOICE_SERVICE_SHARED_SECRET="test-secret",
)
class StartCallTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="a@example.com", email="a@example.com")

    @mock.patch("voicecalls.services.requests.post")
    def test_success_creates_active_session(self, mock_post):
        mock_post.side_effect = _daily_and_bot_side_effect()

        session, user_token = services.start_call(self.user)

        self.assertEqual(session.status, VoiceCallSession.Status.ACTIVE)
        self.assertEqual(session.room_url, "https://x.daily.co/rp-test123")
        self.assertEqual(user_token, "user-token")
        self.assertIsNotNone(session.started_at)

    @mock.patch("voicecalls.services.requests.post")
    def test_second_call_while_one_active_is_rejected(self, mock_post):
        mock_post.side_effect = _daily_and_bot_side_effect()
        services.start_call(self.user)

        with self.assertRaises(services.VoiceCallAlreadyActiveError):
            services.start_call(self.user)

    @override_settings(DAILY_API_KEY="")
    def test_missing_daily_key_raises(self):
        with self.assertRaises(services.VoiceCallError):
            services.start_call(self.user)

    @mock.patch("voicecalls.services.requests.post")
    def test_voice_bot_failure_marks_session_failed(self, mock_post):
        responses = _daily_and_bot_side_effect()
        # Make the final (start-bot) call raise a connection error.
        import requests as requests_module

        responses[-1] = requests_module.RequestException("connection refused")
        mock_post.side_effect = responses

        with self.assertRaises(services.VoiceCallError):
            services.start_call(self.user)

        session = VoiceCallSession.objects.get(user=self.user)
        self.assertEqual(session.status, VoiceCallSession.Status.FAILED)


class CompleteCallTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="b@example.com", email="b@example.com")
        self.session = VoiceCallSession.objects.create(
            user=self.user, room_name="rp-test", room_url="https://x.daily.co/rp-test"
        )
        self.transcript = "User: I'm okay today.\nAssistant: Good to hear."

    @mock.patch("companion.services.ai_engine.assess_checkin")
    @mock.patch("voicecalls.services.ai_engine.summarize_conversation")
    def test_stores_summary_not_full_transcript(self, mock_summarize, mock_assess):
        from companion.schemas import CompanionAssessment

        mock_summarize.return_value = "Reported feeling okay."
        mock_assess.return_value = CompanionAssessment(
            message="Great to hear.", risk_level="low", suggested_action="Keep it up."
        )

        checkin = services.complete_call(self.session, self.transcript, crisis_detected_live=False)

        self.assertEqual(checkin.voice_transcript, "Reported feeling okay.")
        self.assertEqual(checkin.input_method, MoodCheckIn.InputMethod.CALL)
        # The assessment call must have seen the FULL transcript, not the summary.
        _, kwargs = mock_assess.call_args
        self.assertEqual(kwargs["voice_transcript"], self.transcript)

        self.session.refresh_from_db()
        self.assertEqual(self.session.status, VoiceCallSession.Status.COMPLETED)
        self.assertEqual(self.session.checkin_id, checkin.id)

    @mock.patch("companion.services.ai_engine.assess_checkin")
    @mock.patch("voicecalls.services.ai_engine.summarize_conversation")
    def test_force_crisis_overrides_risk_regardless_of_llm(self, mock_summarize, mock_assess):
        from companion.schemas import CompanionAssessment

        mock_summarize.return_value = "Reported feeling okay."
        mock_assess.return_value = CompanionAssessment(
            message="Sounds fine.", risk_level="low", suggested_action="Carry on."
        )

        checkin = services.complete_call(self.session, self.transcript, crisis_detected_live=True)

        response = checkin.companion_response
        self.assertEqual(response.risk_level, "high")
        self.assertTrue(response.crisis_flag)

        self.session.refresh_from_db()
        self.assertTrue(self.session.crisis_detected_live)

    @mock.patch("companion.services.ai_engine.assess_checkin")
    @mock.patch("voicecalls.services.ai_engine.summarize_conversation")
    def test_summary_failure_falls_back_without_blocking_checkin(self, mock_summarize, mock_assess):
        from companion.schemas import CompanionAssessment

        mock_summarize.side_effect = AIEngineError("boom")
        mock_assess.return_value = CompanionAssessment(
            message="Hi.", risk_level="low", suggested_action="Rest."
        )

        checkin = services.complete_call(self.session, self.transcript, crisis_detected_live=False)

        self.assertTrue(checkin.voice_transcript)  # fallback text, not empty/crashed
