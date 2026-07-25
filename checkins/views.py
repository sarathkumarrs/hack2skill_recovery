import json

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from caregivers.models import CaregiverLink
from companion.services import create_companion_response

from .models import MoodCheckIn
from .services import create_checkin, update_streak

VALID_MOODS = {choice for choice, _ in MoodCheckIn.Mood.choices}


@login_required
@require_POST
def checkin_create(request):
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    mood = (data.get("mood") or "").strip() or None
    voice_transcript = (data.get("voice_transcript") or "").strip() or None

    if not mood and not voice_transcript:
        return JsonResponse(
            {"error": "Provide a mood tap or a voice transcript."}, status=400
        )

    if mood and mood not in VALID_MOODS:
        return JsonResponse({"error": f"Unknown mood '{mood}'."}, status=400)

    if voice_transcript:
        input_method = MoodCheckIn.InputMethod.VOICE
        # Hold-to-talk doesn't require a separate emoji tap — the transcript
        # itself carries the emotional signal the AI engine analyzes; "okay"
        # is a neutral placeholder bucket, not a claim about how they feel.
        mood = mood or MoodCheckIn.Mood.OKAY
    else:
        input_method = MoodCheckIn.InputMethod.TAP

    checkin = create_checkin(
        user=request.user,
        mood=mood,
        input_method=input_method,
        voice_transcript=voice_transcript,
    )
    update_streak(request.user, checkin.local_date)
    create_companion_response(checkin)

    return JsonResponse(
        {"redirect_url": reverse("checkin_response", args=[checkin.id])}
    )


@login_required
def checkin_response(request, checkin_id):
    checkin = get_object_or_404(
        MoodCheckIn, id=checkin_id, user=request.user
    )
    response = getattr(checkin, "companion_response", None)
    has_active_caregiver = CaregiverLink.objects.filter(
        patient=request.user, status=CaregiverLink.Status.ACTIVE
    ).exists()
    return render(
        request,
        "checkins/response.html",
        {
            "checkin": checkin,
            "response": response,
            "crisis_hotline_text": settings.CRISIS_HOTLINE_TEXT,
            "has_active_caregiver": has_active_caregiver,
        },
    )
