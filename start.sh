#!/usr/bin/env bash

# 1. Run database migrations to set up your Neon database tables
python manage.py db migrate

# 2. Start the Celery crawler in the background (the "&" symbol is what makes it run in the background)
celery -A workers.tasks worker --beat --loglevel=info -c 2 &

# 3. Start the FastAPI web server
uvicorn app:app --host 0.0.0.0 --port $PORT
