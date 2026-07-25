from django.http import JsonResponse
from django.shortcuts import render


def placeholder(request):
    """Phase 0 sanity-check view — replaced by the real Splash/Home views in Phase 1."""
    return render(request, "core/placeholder.html")


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
