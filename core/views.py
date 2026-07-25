from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render

from checkins.models import StreakRecord


def splash(request):
    """Entry point: real users go straight to Home / login, per the PRD's
    Splash → Home flow — no need to make an authenticated user look at
    branding every visit."""
    if request.user.is_authenticated:
        return redirect("home")
    return render(request, "core/splash.html")


@login_required
def home(request):
    """Home screen: greeting, emoji check-in buttons, mic button, streak."""
    streak = StreakRecord.objects.filter(user=request.user).first()
    current_streak = streak.current_streak if streak else 0
    return render(request, "core/home.html", {"current_streak": current_streak})


def manifest(request):
    """Minimal PWA manifest. Icons/full offline behavior land in Phase 4."""
    return JsonResponse(
        {
            "name": "Recovery Pulse",
            "short_name": "Recovery Pulse",
            "start_url": "/",
            "display": "standalone",
            "background_color": "#f0fdfa",
            "theme_color": "#0f766e",
            "icons": [],
        }
    )
