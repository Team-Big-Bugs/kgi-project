# Smart Nudge

Smart Nudge is a mobile-first web MVP for the KGI take-home prompt. It focuses on the "Smart Nudge" notification engine: scheduling contextual reminders, respecting DND windows, dispatching through multiple channels, and tracking whether the agent comes back into the app.

## Stack

- FastAPI
- Jinja2 templates
- SQLAlchemy + Alembic
- SQLite for local development
- PostgreSQL for deployment
- Tailwind/daisyUI-inspired UI layer with custom CSS tokens
- Standard Web Push, SMTP email, and LINE Messaging API hooks

## Features

- Agent dashboard, assignments, preferences, history, and LINE linking flow
- Admin dashboard, template builder, dispatch log view, assignment overview, and scheduler monitor
- Background scheduler service with dedupe protection and DND handling
- Notification template rendering with placeholder support
- Dispatch logging plus click/open tracking
- LINE webhook linking using one-time link codes
- Custom 404 and 500 pages

## Local Setup

1. Create and activate a virtual environment.
2. Install dependencies.
3. Copy `.env.example` to `.env` and adjust values if needed.
4. Run the database migration.
5. Seed demo data.
6. Start the app.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
python scripts/seed_demo_data.py
uvicorn app.main:app --reload
```

Open [http://127.0.0.1:8000/auth/login](http://127.0.0.1:8000/auth/login).

## Demo Accounts

- Agent: `lin.agent@smartnudge.example` / `agent1234`
- Admin: `admin@smartnudge.example` / `admin1234`

## Scheduler

Run the scheduler locally with:

```bash
python scripts/run_scheduler.py
```

In production, Railway Cron should run the same command every 5 minutes.

## Environment Notes

### Local

- `DATABASE_URL=sqlite:///./dev.db`
- Web Push works only in browsers that support service workers and notifications.
- LINE webhook testing requires a public HTTPS URL.

### Production

- Use Railway for the app and cron.
- Use Supabase PostgreSQL for `DATABASE_URL`.
- Keep secrets in Railway environment variables.
- Configure Railway Cron to run `python scripts/run_scheduler.py`.

## Important Env Vars

- `DATABASE_URL`
- `SECRET_KEY`
- `CRON_SECRET`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`
- `VAPID_PUBLIC_KEY`
- `VAPID_PRIVATE_KEY`
- `VAPID_SUBJECT`
- `LINE_CHANNEL_SECRET`
- `LINE_CHANNEL_ACCESS_TOKEN`
- `LINE_OFFICIAL_ACCOUNT_URL`
- `LINE_OFFICIAL_ACCOUNT_QR_URL`

## Tests

Run the route suite with:

```bash
python -m unittest tests.test_routes
```

## Deployment Notes

- Local development uses SQLite because it is fast and zero-config.
- Deployment should use PostgreSQL; SQLAlchemy keeps the model layer portable.
- The LINE webhook endpoint is `POST /line/webhook`.
- Tracking redirect endpoint is `GET /track/{tracking_token}`.

## Current Scope

This MVP intentionally treats assignment due dates and peak learning times as upstream inputs. The project focuses on the notification engine rather than implementing the reinforcement-learning algorithm itself.
