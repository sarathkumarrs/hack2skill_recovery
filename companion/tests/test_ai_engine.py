from unittest import mock

import anthropic
from django.test import SimpleTestCase, override_settings

from companion import ai_engine
from companion.schemas import CompanionAssessment


class AssessCheckinTests(SimpleTestCase):
    def setUp(self):
        # Reset the lazily-created client singleton between tests.
        ai_engine._client = None

    def test_missing_api_key_raises_before_calling_client(self):
        with override_settings(ANTHROPIC_API_KEY=""):
            with self.assertRaises(ai_engine.AIEngineError):
                ai_engine.assess_checkin(
                    mood="good", mood_history=[], voice_transcript=None, streak=0
                )

    @override_settings(ANTHROPIC_API_KEY="test-key")
    def test_successful_call_returns_parsed_assessment_and_builds_expected_prompt(self):
        expected = CompanionAssessment(
            message="Great job", risk_level="low", suggested_action="Take a walk"
        )
        mock_response = mock.Mock(stop_reason="end_turn", parsed_output=expected)
        mock_client = mock.Mock()
        mock_client.messages.parse.return_value = mock_response

        with mock.patch.object(ai_engine, "_get_client", return_value=mock_client):
            result = ai_engine.assess_checkin(
                mood="good",
                mood_history=["okay", "struggling"],
                voice_transcript="feeling better today",
                streak=3,
            )

        self.assertEqual(result, expected)
        _, kwargs = mock_client.messages.parse.call_args
        self.assertEqual(kwargs["output_format"], CompanionAssessment)
        self.assertEqual(kwargs["system"], ai_engine.SYSTEM_PROMPT)
        user_content = kwargs["messages"][0]["content"]
        self.assertIn("Current mood: good", user_content)
        self.assertIn("okay, struggling", user_content)
        self.assertIn("feeling better today", user_content)
        self.assertIn("3 day(s)", user_content)

    @override_settings(ANTHROPIC_API_KEY="test-key")
    def test_refusal_stop_reason_raises_ai_engine_error(self):
        mock_response = mock.Mock(stop_reason="refusal", parsed_output=None)
        mock_client = mock.Mock()
        mock_client.messages.parse.return_value = mock_response

        with mock.patch.object(ai_engine, "_get_client", return_value=mock_client):
            with self.assertRaises(ai_engine.AIEngineError):
                ai_engine.assess_checkin(
                    mood="craving", mood_history=[], voice_transcript=None, streak=0
                )

    @override_settings(ANTHROPIC_API_KEY="test-key")
    def test_malformed_structured_output_raises_ai_engine_error(self):
        mock_response = mock.Mock(stop_reason="end_turn", parsed_output=None)
        mock_client = mock.Mock()
        mock_client.messages.parse.return_value = mock_response

        with mock.patch.object(ai_engine, "_get_client", return_value=mock_client):
            with self.assertRaises(ai_engine.AIEngineError):
                ai_engine.assess_checkin(
                    mood="good", mood_history=[], voice_transcript=None, streak=0
                )

    @override_settings(ANTHROPIC_API_KEY="test-key")
    def test_connection_error_raises_ai_engine_error(self):
        mock_client = mock.Mock()
        mock_client.messages.parse.side_effect = anthropic.APIConnectionError(
            request=mock.Mock()
        )

        with mock.patch.object(ai_engine, "_get_client", return_value=mock_client):
            with self.assertRaises(ai_engine.AIEngineError):
                ai_engine.assess_checkin(
                    mood="good", mood_history=[], voice_transcript=None, streak=0
                )


class SummarizeConversationTests(SimpleTestCase):
    def setUp(self):
        ai_engine._client = None

    def test_missing_api_key_raises(self):
        with override_settings(ANTHROPIC_API_KEY=""):
            with self.assertRaises(ai_engine.AIEngineError):
                ai_engine.summarize_conversation("User: hi\nAssistant: hello")

    @override_settings(ANTHROPIC_API_KEY="test-key")
    def test_empty_transcript_short_circuits_without_calling_client(self):
        mock_client = mock.Mock()
        with mock.patch.object(ai_engine, "_get_client", return_value=mock_client):
            result = ai_engine.summarize_conversation("   ")
        mock_client.messages.create.assert_not_called()
        self.assertTrue(result)

    @override_settings(ANTHROPIC_API_KEY="test-key")
    def test_successful_call_returns_text(self):
        text_block = mock.Mock(type="text", text="Reported feeling okay today.")
        mock_response = mock.Mock(stop_reason="end_turn", content=[text_block])
        mock_client = mock.Mock()
        mock_client.messages.create.return_value = mock_response

        with mock.patch.object(ai_engine, "_get_client", return_value=mock_client):
            result = ai_engine.summarize_conversation("User: I'm okay.\nAssistant: Good.")

        self.assertEqual(result, "Reported feeling okay today.")
        _, kwargs = mock_client.messages.create.call_args
        self.assertEqual(kwargs["system"], ai_engine.SUMMARY_SYSTEM_PROMPT)

    @override_settings(ANTHROPIC_API_KEY="test-key")
    def test_refusal_raises(self):
        mock_response = mock.Mock(stop_reason="refusal", content=[])
        mock_client = mock.Mock()
        mock_client.messages.create.return_value = mock_response

        with mock.patch.object(ai_engine, "_get_client", return_value=mock_client):
            with self.assertRaises(ai_engine.AIEngineError):
                ai_engine.summarize_conversation("some transcript")
