# Deploying Recovery Pulse

## Important: SQLite does not survive on DigitalOcean App Platform

Earlier in this project we chose **SQLite** because this is a 1–2 user MVP —
that part is still fine. But **App Platform containers are ephemeral**: the
local filesystem (including `db.sqlite3`) is wiped on every deploy, restart,
or scale event. If you deploy this app to App Platform as-is, your users'
check-ins will silently disappear the next time you push a change or the
container restarts. There is no persistent-volume option for App Platform web
services (that's a Droplet+Volumes feature).

You have two honest options — pick based on how much you value "just use
SQLite" vs. "just use App Platform":

**Option A — Deploy on a Droplet instead of App Platform (keeps SQLite).**
A plain Ubuntu Droplet has a real, persistent disk, so `db.sqlite3` survives
restarts and redeploys exactly like it does on your laptop. More manual setup
(you run gunicorn + nginx + systemd yourself, or use a tool like
[dokku](https://dokku.com/)), but zero architecture change.

**Option B — Deploy on App Platform, but switch to Managed PostgreSQL.**
If you specifically want App Platform's convenience (git-push deploys, no
server management), add a DigitalOcean Managed Database (Postgres, cheapest
tier) and change `DATABASES` in `settings.py` to point at it via `dj-database-url`
or `django-environ`'s `env.db()`. This is a real (small) architecture change,
not just a config flip — plan for it before you have real user data to migrate.

Neither option is wired up in this repo yet — pick one and say so before we
wire up the actual `DATABASES` config or app spec for it.

---

## Environment variables (both options)

Copy `.env.example` to `.env` on the server (or set these as App Platform /
your process manager's environment variables — never commit real values):

| Variable | Notes |
|---|---|
| `SECRET_KEY` | Generate a real random value — `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `DEBUG` | `False` in production |
| `ALLOWED_HOSTS` | Your real domain(s), comma-separated |
| `CSRF_TRUSTED_ORIGINS` | e.g. `https://yourdomain.com` — required behind a proxy that terminates TLS |
| `ANTHROPIC_API_KEY` | Real Claude API key — the AI companion silently falls back to the safety floor without one, so users get generic responses, not an error |
| `ANTHROPIC_MODEL` | `claude-haiku-4-5` (default) — measured live at ~2.7s/call vs Opus 5's ~6s; see `companion/ai_engine.py` |
| `ELEVENLABS_API_KEY` / `ELEVENLABS_VOICE_ID` / `ELEVENLABS_MODEL_ID` | Text-to-speech for the "Listen" button. Voice ID must come from your own account's `GET /v1/voices` — free-tier keys can't use every public-library voice |
| `VAPID_PRIVATE_KEY` / `VAPID_PUBLIC_KEY` | Generate your own for production — do not reuse the dev keypair from local testing. See "Generating VAPID keys" below. |
| `VAPID_CLAIMS_EMAIL` | `mailto:you@yourdomain.com` |
| `CRISIS_HOTLINE_TEXT` / `CRISIS_HOTLINE_NUMBER` | Localize for your actual user base — the 988 US lifeline default is a placeholder, not a universal answer |
| `SECURE_SSL_REDIRECT` | `True` once HTTPS is actually working end-to-end (default `True` when `DEBUG=False`) |
| `DAILY_API_KEY` / `DEEPGRAM_API_KEY` | Live voice call — WebRTC transport (Daily) and streaming speech-to-text (Deepgram). See "Live voice call" below. |
| `VOICE_SERVICE_URL` / `VOICE_SERVICE_SHARED_SECRET` / `DJANGO_BASE_URL` | How Django and the `voice_bot/` service reach each other — see "Live voice call" below |
| `MAX_CALL_DURATION_SECONDS` / `CRISIS_SCRIPTED_RESPONSE` | Call length cap (default 600s) and the fixed crisis message the bot speaks when the real-time keyword monitor fires |

### Generating VAPID keys

```python
import base64
from cryptography.hazmat.primitives.asymmetric import ec

private_key = ec.generate_private_key(ec.SECP256R1())
priv_numbers = private_key.private_numbers()
priv_b64 = base64.urlsafe_b64encode(priv_numbers.private_value.to_bytes(32, "big")).rstrip(b"=").decode()

pub_numbers = private_key.public_key().public_numbers()
pub_bytes = b"\x04" + pub_numbers.x.to_bytes(32, "big") + pub_numbers.y.to_bytes(32, "big")
pub_b64 = base64.urlsafe_b64encode(pub_bytes).rstrip(b"=").decode()

print("VAPID_PRIVATE_KEY=" + priv_b64)
print("VAPID_PUBLIC_KEY=" + pub_b64)
```

---

## Build & run

```sh
pip install -r requirements.txt
python manage.py collectstatic --noinput   # required — WhiteNoise's manifest storage needs this
python manage.py migrate
gunicorn recovery.wsgi --bind 0.0.0.0:$PORT --workers 3   # see Procfile
```

## Live voice call — a second, always-running process

The "Start Call" feature (`voicecalls/` + `voice_bot/`) is **not** part of
the Django web process — real-time audio can't live inside a normal request/
response cycle. `voice_bot/` is a separate FastAPI service that must be
running continuously alongside Django, in the same virtualenv (it calls
`django.setup()` on startup to reuse `companion.risk_rules` and
`companion.ai_engine.SYSTEM_PROMPT` directly — zero drift on the
safety-critical logic).

```sh
uvicorn voice_bot.main:app --host 0.0.0.0 --port 7860   # see the `voice` line in Procfile
```

Django reaches this service via `VOICE_SERVICE_URL`; the service reaches
Django's completion webhook via `DJANGO_BASE_URL`. Both directions are
authenticated with the same `VOICE_SERVICE_SHARED_SECRET` (generate one,
don't leave it blank in production — the webhook endpoint rejects requests
without a valid secret).

- **Droplet**: one more systemd unit (or one more process for `dokku`/
  whatever process manager you're using) alongside gunicorn.
- **App Platform**: a **second service component** (not a Job — this is
  long-running, unlike the reminder command below), independently scaled/
  billed, with its own `DAILY_API_KEY`/`DEEPGRAM_API_KEY`/
  `VOICE_SERVICE_SHARED_SECRET` set on *that* component. Point the web
  component's `VOICE_SERVICE_URL` at the voice component's internal
  address (App Platform's service-to-service DNS), not a public URL —
  getting this binding wrong is the most likely first-deploy bug here.

Django itself never touches real-time audio and never writes to the
database from the voice service's process — `voicecalls/` only ever talks
to `voice_bot/` over plain HTTP, in both directions.

## Daily reminder job

`send_daily_checkin_reminders` is a polling management command, not a
long-running process. Run it on a schedule — every ~15 minutes is plenty:

```sh
python manage.py send_daily_checkin_reminders
```

- **Droplet**: a cron entry or systemd timer.
- **App Platform**: an App Platform "Job" component (scheduled), running the
  same command, alongside the web service component.

## Before real users touch this

- [ ] Pick Option A or B above and wire up the real database config
- [ ] Real check-in round trip measured live at ~2.3–3.6s on `claude-haiku-4-5`
      (vs. Opus 5's ~6s+) — close to the PRD's <2s target but not fully
      there; revisit if that last margin matters (see README)
- [ ] Generate fresh production VAPID keys (don't reuse dev ones)
- [ ] Review and localize the crisis-keyword list in `companion/risk_rules.py`
      and the crisis hotline text — both are starting points, not
      clinically reviewed
- [ ] Replace `static/core/icons/icon.svg` with real brand assets
- [ ] Set up `db.sqlite3` backups if going with Option A (a Droplet's disk
      isn't backed up by default either — e.g. a cron job that copies the
      file to DO Spaces on a schedule)
- [ ] Get real `DAILY_API_KEY` / `DEEPGRAM_API_KEY` and generate a real
      `VOICE_SERVICE_SHARED_SECRET`; confirm `voice_bot/` is actually running
      as its own long-lived process before "Start Call" goes live — it fails
      closed (a clean error, not a hang) if not, but still worth checking
- [ ] Place a real end-to-end test call, including deliberately saying a
      crisis phrase mid-call, to confirm the scripted safety override fires
      correctly (see the plan's Phase 3 verification notes once the real
      Pipecat pipeline replaces the current stub `voice_bot/main.py`)
