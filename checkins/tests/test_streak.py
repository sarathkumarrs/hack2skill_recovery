import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from checkins.models import MoodCheckIn, StreakRecord
from checkins.services import consecutive_bad_days, update_streak

User = get_user_model()


class UpdateStreakTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="a@example.com", email="a@example.com")
        self.day1 = datetime.date(2026, 1, 1)

    def test_first_ever_checkin_starts_streak_at_one(self):
        streak = update_streak(self.user, self.day1)
        self.assertEqual(streak.current_streak, 1)
        self.assertEqual(streak.longest_streak, 1)
        self.assertEqual(streak.last_checkin_date, self.day1)

    def test_consecutive_day_increments_streak(self):
        update_streak(self.user, self.day1)
        streak = update_streak(self.user, self.day1 + datetime.timedelta(days=1))
        self.assertEqual(streak.current_streak, 2)
        self.assertEqual(streak.longest_streak, 2)

    def test_same_day_repeat_checkin_does_not_double_count(self):
        update_streak(self.user, self.day1)
        streak = update_streak(self.user, self.day1)
        self.assertEqual(streak.current_streak, 1)

    def test_skipped_day_resets_streak_to_one(self):
        update_streak(self.user, self.day1)
        update_streak(self.user, self.day1 + datetime.timedelta(days=1))
        # Skip a day entirely, then check in again.
        streak = update_streak(self.user, self.day1 + datetime.timedelta(days=3))
        self.assertEqual(streak.current_streak, 1)
        self.assertEqual(streak.longest_streak, 2)  # longest streak is preserved

    def test_longest_streak_only_ever_increases(self):
        for offset in range(5):
            update_streak(self.user, self.day1 + datetime.timedelta(days=offset))
        # Break the streak, then rebuild a shorter one.
        update_streak(self.user, self.day1 + datetime.timedelta(days=10))
        streak = StreakRecord.objects.get(user=self.user)
        self.assertEqual(streak.current_streak, 1)
        self.assertEqual(streak.longest_streak, 5)


class ConsecutiveBadDaysTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="b@example.com", email="b@example.com")
        self.day1 = datetime.date(2026, 1, 1)

    def _checkin(self, date, mood):
        MoodCheckIn.objects.create(
            user=self.user,
            mood=mood,
            input_method=MoodCheckIn.InputMethod.TAP,
            local_date=date,
        )

    def test_no_checkins_is_zero(self):
        self.assertEqual(consecutive_bad_days(self.user, self.day1), 0)

    def test_single_bad_day_counts_as_one(self):
        self._checkin(self.day1, MoodCheckIn.Mood.STRUGGLING)
        self.assertEqual(consecutive_bad_days(self.user, self.day1), 1)

    def test_good_day_breaks_the_count(self):
        self._checkin(self.day1, MoodCheckIn.Mood.GOOD)
        self.assertEqual(consecutive_bad_days(self.user, self.day1), 0)

    def test_two_consecutive_bad_days_counts_as_two(self):
        self._checkin(self.day1, MoodCheckIn.Mood.CRAVING)
        self._checkin(self.day1 + datetime.timedelta(days=1), MoodCheckIn.Mood.STRUGGLING)
        self.assertEqual(
            consecutive_bad_days(self.user, self.day1 + datetime.timedelta(days=1)), 2
        )

    def test_gap_day_resets_the_count(self):
        self._checkin(self.day1, MoodCheckIn.Mood.CRAVING)
        self._checkin(self.day1 + datetime.timedelta(days=2), MoodCheckIn.Mood.CRAVING)
        # day1+1 has no check-in at all, so the streak from day1 doesn't reach day1+2
        self.assertEqual(
            consecutive_bad_days(self.user, self.day1 + datetime.timedelta(days=2)), 1
        )
