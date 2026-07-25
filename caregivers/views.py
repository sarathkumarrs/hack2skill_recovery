from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from checkins.models import MoodCheckIn, StreakRecord

from .models import CaregiverInvite, CaregiverLink
from .services import notify_caregivers_for_checkin

MOOD_EMOJI = {
    MoodCheckIn.Mood.GOOD: "😊",
    MoodCheckIn.Mood.OKAY: "😐",
    MoodCheckIn.Mood.STRUGGLING: "😞",
    MoodCheckIn.Mood.CRAVING: "😣",
}


@login_required
def invite_create(request):
    """Shows a shareable invite link, reusing any still-valid pending invite
    rather than minting a new one on every visit."""
    invite = CaregiverInvite.objects.filter(
        patient=request.user, status=CaregiverInvite.Status.PENDING
    ).first()
    if invite is None or not invite.is_valid():
        invite = CaregiverInvite.objects.create(patient=request.user)

    invite_url = request.build_absolute_uri(
        reverse("caregiver_invite_accept", args=[invite.invite_code])
    )
    return render(
        request, "caregivers/invite.html", {"invite": invite, "invite_url": invite_url}
    )


@login_required
def invite_accept(request, code):
    invite = get_object_or_404(CaregiverInvite, invite_code=code)

    if invite.patient_id == request.user.id:
        messages.error(request, "You can't accept your own invite.")
        return redirect("home")

    if not invite.is_valid():
        return render(request, "caregivers/accept_invite.html", {"invite": None})

    if request.method == "POST":
        CaregiverLink.objects.update_or_create(
            patient=invite.patient,
            caregiver=request.user,
            defaults={"status": CaregiverLink.Status.ACTIVE},
        )
        invite.status = CaregiverInvite.Status.ACCEPTED
        invite.save(update_fields=["status"])
        return redirect("caregiver_dashboard")

    return render(request, "caregivers/accept_invite.html", {"invite": invite})


@login_required
def dashboard(request):
    links = CaregiverLink.objects.filter(
        caregiver=request.user, status=CaregiverLink.Status.ACTIVE
    ).select_related("patient", "patient__profile")

    patients = []
    for link in links:
        patient = link.patient
        latest_checkin = (
            MoodCheckIn.objects.filter(user=patient).order_by("-created_at").first()
        )
        streak = StreakRecord.objects.filter(user=patient).first()
        patients.append(
            {
                "display_name": patient.profile.display_name or patient.get_username(),
                "latest_checkin": latest_checkin,
                "mood_emoji": MOOD_EMOJI.get(latest_checkin.mood, "") if latest_checkin else "",
                "latest_response": getattr(latest_checkin, "companion_response", None)
                if latest_checkin
                else None,
                "current_streak": streak.current_streak if streak else 0,
            }
        )

    return render(
        request,
        "caregivers/dashboard.html",
        {"patients": patients, "vapid_public_key": settings.VAPID_PUBLIC_KEY},
    )


@login_required
@require_POST
def notify_caregiver(request, checkin_id):
    checkin = get_object_or_404(MoodCheckIn, id=checkin_id, user=request.user)
    has_any_link = CaregiverLink.objects.filter(
        patient=request.user, status=CaregiverLink.Status.ACTIVE
    ).exists()
    notifications = notify_caregivers_for_checkin(checkin)

    if notifications:
        status = "notified"
    elif has_any_link:
        status = "already_notified"
    else:
        status = "no_active_caregiver"

    return JsonResponse(
        {
            "status": status,
            "count": len(notifications),
        }
    )
