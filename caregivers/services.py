"""Caregiver notification: creates the dashboard-visible record and makes a
best-effort real-time Web Push attempt to the caregiver's own subscribed
device. The dashboard record is the reliable channel — push is a bonus, not
a guarantee — so a failed/absent push subscription never blocks the record
from being created."""

from __future__ import annotations

import json

from django.conf import settings
from pywebpush import WebPushException, webpush

from checkins.models import MoodCheckIn
from notifications.models import PushSubscription

from .models import CaregiverLink, CaregiverNotification


def _push_to_caregiver(caregiver, message: str) -> bool:
    subscriptions = PushSubscription.objects.filter(user=caregiver)
    if not subscriptions:
        return False

    payload = json.dumps(
        {"title": "Recovery Pulse", "body": message, "url": "/caregivers/dashboard/"}
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
        except WebPushException:
            continue  # best-effort — the dashboard record is what's reliable
    return delivered


def notify_caregivers_for_checkin(checkin: MoodCheckIn) -> list[CaregiverNotification]:
    """Idempotent per (checkin, caregiver_link) — tapping "Notify Caregiver"
    twice on the same check-in doesn't create duplicate records or re-push."""
    links = CaregiverLink.objects.filter(
        patient=checkin.user, status=CaregiverLink.Status.ACTIVE
    )
    patient_name = checkin.user.profile.display_name or checkin.user.get_username()
    message = (
        f"{patient_name} reported feeling {checkin.get_mood_display().lower()} "
        "today. A supportive check-in may help."
    )

    created = []
    for link in links:
        notification, was_created = CaregiverNotification.objects.get_or_create(
            checkin=checkin,
            caregiver_link=link,
            defaults={
                "message_snapshot": message,
                "channel": CaregiverNotification.Channel.DASHBOARD,
            },
        )
        if not was_created:
            continue

        if _push_to_caregiver(link.caregiver, message):
            notification.channel = CaregiverNotification.Channel.PUSH
            notification.save(update_fields=["channel"])

        created.append(notification)

    return created
