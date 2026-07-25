import json

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .forms import NotificationPreferenceForm
from .models import NotificationPreference, PushSubscription


@login_required
@require_POST
def subscribe(request):
    """Upserts a browser's push subscription. Called by push.js after the
    user grants notification permission — used for both the patient's daily
    reminder opt-in and the caregiver's real-time-alert opt-in (Phase 5)."""
    try:
        data = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    endpoint = data.get("endpoint")
    keys = data.get("keys") or {}
    p256dh = keys.get("p256dh")
    auth = keys.get("auth")
    if not endpoint or not p256dh or not auth:
        return JsonResponse({"error": "Missing subscription fields."}, status=400)

    PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={
            "user": request.user,
            "p256dh": p256dh,
            "auth": auth,
            "user_agent": request.META.get("HTTP_USER_AGENT", "")[:255],
        },
    )
    return JsonResponse({"status": "subscribed"})


@login_required
def preferences(request):
    pref, _ = NotificationPreference.objects.get_or_create(user=request.user)
    if request.method == "POST":
        form = NotificationPreferenceForm(request.POST, instance=pref)
        if form.is_valid():
            form.save()
            return redirect("notification_preferences")
    else:
        form = NotificationPreferenceForm(instance=pref)

    return render(
        request,
        "notifications/preferences.html",
        {"form": form, "vapid_public_key": settings.VAPID_PUBLIC_KEY},
    )
