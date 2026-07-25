# Recovery Pulse

A zero-typing, AI-powered daily check-in companion for people recovering from
substance use disorders. One emoji tap, or a live voice call with the AI
companion, is enough to log how someone's feeling; the companion responds
with support, a relapse-risk read, and one suggested action, and a caregiver
can be looped in with explicit consent. Full product spec in [`PRD.pdf`](PRD.pdf).

## Features

- **One-tap mood check-in** — 😊 Good / 😐 Okay / 😞 Struggling / 😣 Craving
- **Live voice call** — a real-time, conversational voice call with the AI
  companion ([Pipecat](https://github.com/pipecat-ai/pipecat), self-hosted,
  not a third-party hosted agent — see "Live voice call" below), replacing a
  simpler hold-to-talk button. Ends in the same structured check-in record
  as every other input method — a short AI-generated summary is stored, not
  the full transcript.
- **AI recovery companion** — [Claude](https://www.anthropic.com/claude)
  responds like a coach: a supportive message, a relapse-risk level
  (low/medium/high), and one concrete next step
- **Voice replies** — the companion's message can be played back as speech
  ([ElevenLabs](https://elevenlabs.io) text-to-speech)
- **Deterministic safety floor** — the risk level and crisis messaging never
  depend solely on the LLM: a craving mood, a crisis-keyword match in the
  transcript, consecutive bad days, or an AI-engine failure all floor or
  override the risk independently (see `companion/risk_rules.py`)
- **Recovery streak** — daily check-ins build a streak, shown on Home
- **Caregiver consent flow** — a patient invites a caregiver via a shareable
  link; the caregiver gets a dashboard (mood/risk/streak/last check-in) and
  can be notified in real time via Web Push, only when explicitly tapped
- **Push notifications + PWA** — installable app, daily check-in reminder at
  a user-set time, Web Push (VAPID) for both the reminder and caregiver alerts
- **High-contrast mode** and large tap targets for accessibility

## Tech stack

- **Backend**: Django 5.2, server-rendered templates (no separate frontend
  build/API split)
- **Frontend**: Tailwind CSS (via CDN) + vanilla JS
- **Database**: SQLite (deliberate choice for this MVP's scale — see
  [`DEPLOY.md`](DEPLOY.md) before deploying anywhere with an ephemeral
  filesystem)
- **AI**: Anthropic Claude API (`claude-haiku-4-5` — measured live: ~2.7s
  average for this call vs Opus 5's ~6s, and ~5x cheaper for a task this
  simple) for the companion's reasoning; ElevenLabs API for text-to-speech
- **Live voice call**: [Pipecat](https://github.com/pipecat-ai/pipecat)
  (self-hosted — deliberately not ElevenLabs' hosted "Conversational AI",
  so the safety-critical risk logic stays in our own code, not a third
  party's), Daily for WebRTC transport, Deepgram for streaming speech-to-text.
  Runs as a separate standalone service (`voice_bot/`) — see "Live voice
  call" below.
- **Auth**: Django's built-in auth (email/password); Google login
  deliberately deferred
- **Push**: Web Push via VAPID (`pywebpush`), not Firebase
- **Static files**: WhiteNoise
- **Production server**: gunicorn for the web process; uvicorn for the voice
  service (see `Procfile`)

## Project structure

```
recovery/       # Django project settings/urls/wsgi/asgi
core/           # base template, Splash/Home, PWA manifest + service worker
accounts/       # Profile model, signup/login/settings
checkins/       # MoodCheckIn, StreakRecord, the check-in endpoint
companion/      # AI engine (ai_engine.py), safety floor (risk_rules.py),
                # text-to-speech (tts.py), orchestration (services.py)
caregivers/     # CaregiverInvite/Link/Notification, invite + dashboard
notifications/  # PushSubscription, NotificationPreference, reminder command
voicecalls/     # VoiceCallSession, Daily room/token creation, the webhook
                # that turns a finished call into a MoodCheckIn
voice_bot/      # standalone service (NOT a Django app) — runs the live
                # Pipecat pipeline; never touches the database directly
templates/      # all HTML templates, mirroring the app layout above
static/         # JS (checkin.js, voicecall.js, push.js, sw.js) and icons
```

## Getting started

Prerequisites: Python 3.10+.

```sh
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env — see the table below

python manage.py migrate
python manage.py runserver
```

Visit `http://127.0.0.1:8000/`.

### Environment variables

All configuration is via `.env` (gitignored — never commit real secrets).
`.env.example` documents every variable; the important ones:

| Variable | Required for | Notes |
|---|---|---|
| `SECRET_KEY` | Always | Any long random string in dev |
| `ANTHROPIC_API_KEY` | Real AI companion responses | Without it, check-ins still work — the safety floor produces a generic fallback message and floors risk at "medium" rather than erroring |
| `ELEVENLABS_API_KEY` | Voice playback | Without it, the "Listen" button shows "voice playback isn't available" instead of erroring |
| `ELEVENLABS_VOICE_ID` | Voice playback | Must be a voice your own account can use — run `GET /v1/voices` with your key to check; not every public library voice works on a free-tier key |
| `VAPID_PRIVATE_KEY` / `VAPID_PUBLIC_KEY` | Push notifications | Generate your own — see `DEPLOY.md` |
| `CRISIS_HOTLINE_TEXT` / `CRISIS_HOTLINE_NUMBER` | Crisis screen | Defaults to the US 988 lifeline — localize before real launch |
| `DAILY_API_KEY` | Live voice call | From [dashboard.daily.co](https://dashboard.daily.co) — used to create the per-call WebRTC room |
| `DEEPGRAM_API_KEY` | Live voice call | From [deepgram.com](https://deepgram.com) — real-time speech-to-text inside the call |
| `VOICE_SERVICE_SHARED_SECRET` | Live voice call | Generate your own (`python -c "import secrets; print(secrets.token_urlsafe(32))"`) — authenticates Django ↔ `voice_bot/` in both directions |

### Live voice call — a second process

"Start Call" on Home needs `voice_bot/` running **as its own process**,
alongside `manage.py runserver` — real-time audio can't live inside Django's
normal request/response cycle:

```sh
uvicorn voice_bot.main:app --port 7860
```

Without it running, tapping "Start Call" fails with a clean error (not a
hang) — `voicecalls/services.py` marks the session `failed` if it can't
reach `voice_bot/`. `voice_bot/` shares this project's virtualenv and calls
`django.setup()` on startup specifically so it can import
`companion.risk_rules` and `companion.ai_engine.SYSTEM_PROMPT` directly —
the same safety-floor code the rest of the app uses, not a second copy of it.

### Running tests

```sh
python manage.py test
```

Covers the safety-floor rule table (including `force_crisis`, used by the
live-call flow), the AI engine's prompt construction and error handling
(mocked, no live API calls), streak increment/reset logic, the check-in
endpoint's validation and permission boundaries, and the voice-call session
lifecycle (Daily API calls mocked, shared-secret webhook auth, the
summary-vs-full-transcript split).

### Daily reminder job

`send_daily_checkin_reminders` is a polling management command (run it every
~15 minutes via cron/systemd — see `DEPLOY.md`), not a background process:

```sh
python manage.py send_daily_checkin_reminders
```

## Deployment

See [`DEPLOY.md`](DEPLOY.md) — in particular, **do not deploy this as-is to
DigitalOcean App Platform**: its filesystem is ephemeral and will silently
wipe `db.sqlite3` on every redeploy. Pick a Droplet (keeps SQLite) or add
Managed Postgres (if App Platform's convenience matters more) before real
users touch this.

## Before real users touch this

- The check-in round trip has been measured live at ~2.3–3.6s on
  `claude-haiku-4-5` (vs. Opus 5's ~6s+) — closest available to the PRD's
  <2s target, but not fully there. If that last margin matters, look at
  streaming the response instead of waiting for the full message, or
  Fast Mode if you move back to an Opus-tier model
- Review the crisis-keyword list in `companion/risk_rules.py` — it's a
  starting point, not clinically reviewed
- Replace `static/core/icons/icon.svg` with real brand assets
- Localize the crisis hotline text/number for your actual user base
- `voice_bot/main.py` is currently a **stub** — it proves the Django ↔
  voice_bot ↔ Django round trip (real Daily room, real webhook, real
  `MoodCheckIn`/`CompanionResponse`) but doesn't yet run the real Pipecat
  pipeline (Deepgram STT → Claude → ElevenLabs TTS) or the real-time
  crisis-keyword safety processor. No real conversation happens on a call
  yet — replace `_run_stub_call` before this is user-facing.
