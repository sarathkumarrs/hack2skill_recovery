from django.test import SimpleTestCase

from companion.risk_rules import apply_safety_floor, contains_crisis_keyword
from companion.schemas import CompanionAssessment


def assessment(risk_level, message="You're doing okay.", suggested_action="Take a walk."):
    return CompanionAssessment(
        message=message, risk_level=risk_level, suggested_action=suggested_action
    )


class ApplySafetyFloorTests(SimpleTestCase):
    def test_craving_mood_floors_to_at_least_medium(self):
        risk, crisis = apply_safety_floor(
            llm_assessment=assessment("low"), mood="craving", voice_transcript=None
        )
        self.assertEqual(risk, "medium")
        self.assertFalse(crisis)

    def test_craving_mood_does_not_downgrade_a_higher_llm_risk(self):
        risk, crisis = apply_safety_floor(
            llm_assessment=assessment("high"), mood="craving", voice_transcript=None
        )
        self.assertEqual(risk, "high")
        self.assertFalse(crisis)

    def test_crisis_keyword_forces_high_and_crisis_flag_regardless_of_llm(self):
        risk, crisis = apply_safety_floor(
            llm_assessment=assessment("low"),
            mood="good",
            voice_transcript="I just want to give up on everything.",
        )
        self.assertEqual(risk, "high")
        self.assertTrue(crisis)

    def test_crisis_keyword_fires_even_with_no_llm_assessment(self):
        risk, crisis = apply_safety_floor(
            llm_assessment=None,
            mood="good",
            voice_transcript="I can't handle this anymore.",
        )
        self.assertEqual(risk, "high")
        self.assertTrue(crisis)

    def test_missing_llm_assessment_defaults_to_medium_never_low(self):
        risk, crisis = apply_safety_floor(
            llm_assessment=None, mood="good", voice_transcript=None
        )
        self.assertEqual(risk, "medium")
        self.assertFalse(crisis)

    def test_two_consecutive_bad_days_floors_to_at_least_medium(self):
        risk, crisis = apply_safety_floor(
            llm_assessment=assessment("low"),
            mood="okay",
            voice_transcript=None,
            consecutive_bad_days=2,
        )
        self.assertEqual(risk, "medium")
        self.assertFalse(crisis)

    def test_single_bad_day_does_not_trigger_history_floor(self):
        risk, crisis = apply_safety_floor(
            llm_assessment=assessment("low"),
            mood="struggling",
            voice_transcript=None,
            consecutive_bad_days=1,
        )
        # mood itself isn't "craving", and only 1 consecutive bad day —
        # neither the mood floor nor the history floor should fire.
        self.assertEqual(risk, "low")
        self.assertFalse(crisis)

    def test_llm_high_on_a_clean_day_is_preserved(self):
        risk, crisis = apply_safety_floor(
            llm_assessment=assessment("high"), mood="good", voice_transcript=None
        )
        self.assertEqual(risk, "high")
        self.assertFalse(crisis)

    def test_llm_low_on_a_clean_day_stays_low(self):
        risk, crisis = apply_safety_floor(
            llm_assessment=assessment("low"), mood="good", voice_transcript=None
        )
        self.assertEqual(risk, "low")
        self.assertFalse(crisis)

    def test_force_crisis_overrides_regardless_of_llm_or_transcript(self):
        risk, crisis = apply_safety_floor(
            llm_assessment=assessment("low"),
            mood="good",
            voice_transcript="Everything is fine, no concerning words here.",
            force_crisis=True,
        )
        self.assertEqual(risk, "high")
        self.assertTrue(crisis)

    def test_force_crisis_fires_even_with_no_llm_assessment(self):
        risk, crisis = apply_safety_floor(
            llm_assessment=None, mood="good", voice_transcript=None, force_crisis=True
        )
        self.assertEqual(risk, "high")
        self.assertTrue(crisis)

    def test_no_force_crisis_and_no_keyword_does_not_trigger_high(self):
        risk, crisis = apply_safety_floor(
            llm_assessment=assessment("low"),
            mood="good",
            voice_transcript="Everything is fine.",
            force_crisis=False,
        )
        self.assertEqual(risk, "low")
        self.assertFalse(crisis)


class ContainsCrisisKeywordTests(SimpleTestCase):
    def test_matches_known_phrase_case_insensitively(self):
        self.assertTrue(contains_crisis_keyword("I just want to GIVE UP today."))

    def test_no_match_on_unrelated_text(self):
        self.assertFalse(contains_crisis_keyword("I had a pretty good day."))

    def test_none_and_empty_are_false(self):
        self.assertFalse(contains_crisis_keyword(None))
        self.assertFalse(contains_crisis_keyword(""))
