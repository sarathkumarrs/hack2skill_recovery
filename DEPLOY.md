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
| `ANTHROPIC_MODEL` | `claude-opus-5` (default) |
| `VAPID_PRIVATE_KEY` / `VAPID_PUBLIC_KEY` | Generate your own for production — do not reuse the dev keypair from local testing. See "Generating VAPID keys" below. |
| `VAPID_CLAIMS_EMAIL` | `mailto:you@yourdomain.com` |
| `CRISIS_HOTLINE_TEXT` / `CRISIS_HOTLINE_NUMBER` | Localize for your actual user base — the 988 US lifeline default is a placeholder, not a universal answer |
| `SECURE_SSL_REDIRECT` | `True` once HTTPS is actually working end-to-end (default `True` when `DEBUG=False`) |

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
- [ ] Set a real `ANTHROPIC_API_KEY` and manually time a check-in → AI response
      round trip — the PRD's non-functional requirement is under 2 seconds,
      and this hasn't been measured against a live key yet (only the
      safety-floor fallback path has been exercised in development)
- [ ] Generate fresh production VAPID keys (don't reuse dev ones)
- [ ] Review and localize the crisis-keyword list in `companion/risk_rules.py`
      and the crisis hotline text — both are starting points, not
      clinically reviewed
- [ ] Replace `static/core/icons/icon.svg` with real brand assets
- [ ] Set up `db.sqlite3` backups if going with Option A (a Droplet's disk
      isn't backed up by default either — e.g. a cron job that copies the
      file to DO Spaces on a schedule)
