import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone


def _generate_invite_code():
    return secrets.token_urlsafe(8)


def _default_expiry():
    return timezone.now() + timezone.timedelta(days=7)


class CaregiverInvite(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        REVOKED = "revoked", "Revoked"
        EXPIRED = "expired", "Expired"

    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="caregiver_invites_sent", on_delete=models.CASCADE
    )
    invite_code = models.CharField(max_length=32, unique=True, default=_generate_invite_code)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=_default_expiry)

    def is_valid(self):
        return self.status == self.Status.PENDING and timezone.now() < self.expires_at

    def __str__(self):
        return f"Invite from {self.patient} ({self.status})"


class CaregiverLink(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        REVOKED = "revoked", "Revoked"

    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="caregiver_links", on_delete=models.CASCADE
    )
    caregiver = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="patient_links", on_delete=models.CASCADE
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("patient", "caregiver")

    def __str__(self):
        return f"{self.caregiver} ↔ {self.patient} ({self.status})"


class CaregiverNotification(models.Model):
    class Channel(models.TextChoices):
        DASHBOARD = "dashboard", "Dashboard"
        PUSH = "push", "Push"

    checkin = models.ForeignKey(
        "checkins.MoodCheckIn", related_name="caregiver_notifications", on_delete=models.CASCADE
    )
    caregiver_link = models.ForeignKey(
        CaregiverLink, related_name="notifications", on_delete=models.CASCADE
    )
    # Wellness-only text, snapshotted at send time — never a diagnosis, per PRD.
    message_snapshot = models.TextField()
    channel = models.CharField(max_length=16, choices=Channel.choices, default=Channel.DASHBOARD)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("checkin", "caregiver_link")

    def __str__(self):
        return f"Notification to {self.caregiver_link.caregiver} re: {self.checkin}"
