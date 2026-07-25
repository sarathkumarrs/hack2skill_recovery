web: gunicorn recovery.wsgi --bind 0.0.0.0:$PORT --workers 3
voice: uvicorn voice_bot.main:app --host 0.0.0.0 --port $VOICE_PORT
