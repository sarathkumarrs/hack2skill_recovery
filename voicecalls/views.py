import hmac
import json

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import VoiceCallSession
from .services import VoiceCallAlreadyActiveError, VoiceCallError, complete_call, start_call


@login_required
@require_POST
def start(request):
    try:
        session, user_token = start_call(request.user)
    except VoiceCallAlreadyActiveError as exc:
        return JsonResponse({"error": str(exc)}, status=409)
    except VoiceCallError as exc:
        return JsonResponse({"error": str(exc)}, status=503)

    return JsonResponse(
        {"session_id": session.id, "room_url": session.room_url, "user_token": user_token}
    )


def _shared_secret_valid(request) -> bool:
    provided = request.headers.get("X-Voice-Service-Secret", "")
    expected = settings.VOICE_SERVICE_SHARED_SECRET
    if not expected:
        return False
    return hmac.compare_digest(provided, expected)


@csrf_exempt
@require_POST
def webhook_complete(request):
    """Machine-to-machine — called by voice_bot when a call ends. No user
    session; authenticated by shared secret instead."""
    if not _shared_secret_valid(request):
        return JsonResponse({"error": "Invalid or missing shared secret."}, status=403)

    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    session_id = data.get("session_id")
    transcript = data.get("transcript") or ""
    crisis_detected_live = bool(data.get("crisis_detected_live", False))

    session = get_object_or_404(VoiceCallSession, id=session_id)

    try:
        checkin = complete_call(session, transcript, crisis_detected_live)
    except Exception as exc:  # noqa: BLE001 — a lost webhook is the one truly bad outcome here
        session.status = VoiceCallSession.Status.FAILED
        session.save(update_fields=["status"])
        return JsonResponse({"error": f"Failed to complete call: {exc}"}, status=500)

    return JsonResponse({"status": "ok", "checkin_id": checkin.id})


@login_required
def status(request, session_id):
    session = get_object_or_404(VoiceCallSession, id=session_id, user=request.user)

    if session.status == VoiceCallSession.Status.COMPLETED and session.checkin_id:
        return JsonResponse(
            {
                "status": "completed",
                "redirect_url": reverse("checkin_response", args=[session.checkin_id]),
            }
        )
    if session.status == VoiceCallSession.Status.FAILED:
        return JsonResponse({"status": "failed"})

    return JsonResponse({"status": session.status})
