"""
Django settings for recovery project (Recovery Pulse).
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, True),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env(
    "SECRET_KEY",
    default="django-insecure-v%4bzzz%n_gp)5kh!bsezh%&zkqw75xex^m)22z2a3yidj=64^",
)

DEBUG = env("DEBUG")

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
    "accounts",
    "checkins",
    "companion",
    "caregivers",
    "notifications",
    "voicecalls",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "recovery.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "recovery.wsgi.application"


# Database

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


# Password validation

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# Internationalization

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Auth redirects

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "login"


# Recovery Pulse — third-party service config (all via environment, never committed)

ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", default="")
# claude-haiku-4-5, not Opus — measured live: Opus 5 averages ~6s for this
# short classification+generation call even with thinking disabled, vs
# Haiku's ~2.7s. Neither hits the PRD's <2s NFR outright, but Haiku is the
# closest and is also ~5x cheaper for a task this simple. See companion/ai_engine.py.
ANTHROPIC_MODEL = env("ANTHROPIC_MODEL", default="claude-haiku-4-5")

# ElevenLabs (text-to-speech for the AI companion's message) — companion/tts.py
# Voice default is "Sarah" (mature/reassuring) — a free-tier API key can only use
# premade voices returned by GET /v1/voices for that account, not every voice in
# ElevenLabs' public library (e.g. the commonly-referenced "Rachel" ID 404s/402s
# on free tier). Check your own account's /v1/voices before assuming a voice ID works.
ELEVENLABS_API_KEY = env("ELEVENLABS_API_KEY", default="")
ELEVENLABS_VOICE_ID = env("ELEVENLABS_VOICE_ID", default="EXAVITQu4vr4xnSDxMaL")
ELEVENLABS_MODEL_ID = env("ELEVENLABS_MODEL_ID", default="eleven_flash_v2_5")  # low-latency, fits the <2s NFR

VAPID_PRIVATE_KEY = env("VAPID_PRIVATE_KEY", default="")
VAPID_PUBLIC_KEY = env("VAPID_PUBLIC_KEY", default="")
VAPID_CLAIMS_EMAIL = env("VAPID_CLAIMS_EMAIL", default="mailto:admin@example.com")

# Crisis safety floor — swappable/localizable, see companion/risk_rules.py
CRISIS_HOTLINE_TEXT = env(
    "CRISIS_HOTLINE_TEXT", default="988 Suicide & Crisis Lifeline (call or text 988)"
)
CRISIS_HOTLINE_NUMBER = env("CRISIS_HOTLINE_NUMBER", default="988")

# Live voice call (Pipecat) — voicecalls/ (this Django app) talks to the
# standalone voice_bot/ service over HTTP; Django never runs the real-time
# audio pipeline itself. See voice_bot/ and voicecalls/services.py.
DAILY_API_KEY = env("DAILY_API_KEY", default="")
DEEPGRAM_API_KEY = env("DEEPGRAM_API_KEY", default="")
VOICE_SERVICE_URL = env("VOICE_SERVICE_URL", default="http://localhost:7860")
VOICE_SERVICE_SHARED_SECRET = env("VOICE_SERVICE_SHARED_SECRET", default="")
DJANGO_BASE_URL = env("DJANGO_BASE_URL", default="http://localhost:8000")
MAX_CALL_DURATION_SECONDS = env.int("MAX_CALL_DURATION_SECONDS", default=600)
CRISIS_SCRIPTED_RESPONSE = env(
    "CRISIS_SCRIPTED_RESPONSE",
    default=(
        "I hear you, and I want you to know you don't have to go through this "
        "alone. If you're in crisis, please reach out right now: 988 Suicide "
        "& Crisis Lifeline, call or text 988. I'm going to stay on the line "
        "with you."
    ),
)


# Production hardening — only when DEBUG is off. Behind a proxy (DigitalOcean
# App Platform, etc.) that terminates TLS, Django itself sees plain HTTP, so
# SECURE_PROXY_SSL_HEADER tells it to trust the proxy's X-Forwarded-Proto.
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=60 * 60 * 24 * 7)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}
