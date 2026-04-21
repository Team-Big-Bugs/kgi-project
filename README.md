# Smart Nudge

Smart Nudge is a mobile-first web MVP for the KGI Project 8 prompt: a notification engine that nudges insurance/financial agents back into learning at the right moment, through the right channel, with tracking for actual return-to-app behavior.

This project focuses on the notification engine itself:
- channel preference and DND rules
- 15-minute peak learning window checks
- omnichannel dispatch
- queue/log state in a relational database
- tracking-token based conversion logging

## What It Covers

This MVP maps directly to the Project 8 requirements:

- **Agent Preference Center**
  - choose `PUSH`, `EMAIL`, or `LINE`
  - set `Do Not Disturb`
  - set `Peak Learning Hour`
  - opt out for compliance
- **Smart Payload preview**
  - lock-screen style preview on the agent dashboard and preferences page
- **Admin Template Builder**
  - template authoring with placeholders like `{{agent_name}}` and `{{module_title}}`
- **Scheduler / Background Worker**
  - scans due assignments
  - respects DND
  - respects the 15-minute peak window
  - runs every 5 minutes in production
- **Omnichannel dispatch**
  - Standard Web Push
  - LINE Messaging API
  - SMTP email hooks
- **Engagement tracking**
  - every dispatch gets a tracking token
  - clicking the nudge marks `opened_timestamp`
  - admin dashboard shows successful conversions and open rate

## Stack

- FastAPI
- Jinja2 templates
- SQLAlchemy + Alembic
- SQLite for local development
- PostgreSQL for deployment
- Custom CSS UI layer
- Standard Web Push
- LINE Messaging API
- SMTP email support
- Railway + Supabase for production

## Core Product Flow

1. Agent opens the Preference Center.
2. Agent selects a preferred channel and DND window.
3. Scheduler runs every 5 minutes.
4. If an assignment is due and the agent is inside the 15-minute peak window, the scheduler creates a dispatch row.
5. The dispatcher sends the nudge through the agent's preferred channel.
6. The notification contains a tracking link.
7. When the agent clicks the notification, the app marks the dispatch as opened.
8. Admin can review sent/opened conversions from the dashboard and dispatch logs.

## Important Behavior

### One active nudge per agent

To avoid noisy duplicate reminders:

- the scheduler sends **at most one active nudge per agent at a time**
- if an agent has multiple due assignments, only the highest-priority pending one is sent first
- after that dispatch is opened, the next due assignment can be sent on a later scheduler run

### Channel change and re-send behavior

Dispatch dedupe is based on:

- `agent_id`
- `assignment_id`
- `channel_type`
- local scheduled date

That means:

- if the agent changes from `LINE` to `PUSH`, a new dispatch can be created for the same assignment
- if the same assignment and same channel were already sent on the same local day, the scheduler will skip it as a duplicate

## Local Setup

1. Create and activate a virtual environment.
2. Install dependencies.
3. Copy `.env.example` to `.env`.
4. Run migrations.
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

Open:

- [http://127.0.0.1:8000/auth/login](http://127.0.0.1:8000/auth/login)

## Demo Accounts

- Agent: `lin.agent@smartnudge.example` / `agent1234`
- Admin: `admin@smartnudge.example` / `admin1234`

## Local Testing

### Run the scheduler locally

```bash
python scripts/run_scheduler.py
```

### Run the route tests

```bash
python -m unittest tests.test_routes
```

### Web Push sanity checks

From the agent preferences page:

- `Show local notification`
  - verifies browser / OS notification display
- `Send test push`
  - verifies the real web push pipeline through the backend and service worker

## Production Architecture

### Web service

- Railway service name: `kgi-project`
- custom start command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

### Scheduler service

- Railway cron service name: `kgi-scheduler`
- custom start command:

```bash
python scripts/run_scheduler.py
```

- cron schedule:

```txt
*/5 * * * *
```

### Database

- Supabase PostgreSQL
- `DATABASE_URL` should use the pooled connection string
- the deployed SQLAlchemy URL should use:

```txt
postgresql+psycopg://...
```

### Railway pre-deploy

Configured in [railway.json](/Users/sungmin/Desktop/Project/kaggle-housing-price-prediction/kgi-mini-project/railway.json):

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "deploy": {
    "preDeployCommand": "alembic upgrade head",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 5
  }
}
```

## Environment Variables

See [.env.example](/Users/sungmin/Desktop/Project/kaggle-housing-price-prediction/kgi-mini-project/.env.example).

Important values:

- `APP_ENV`
- `APP_BASE_URL`
- `DATABASE_URL`
- `SECRET_KEY`
- `CRON_SECRET`
- `TIMEZONE`
- `VAPID_PUBLIC_KEY`
- `VAPID_PRIVATE_KEY`
- `VAPID_SUBJECT`
- `LINE_CHANNEL_SECRET`
- `LINE_CHANNEL_ACCESS_TOKEN`
- `LINE_OFFICIAL_ACCOUNT_URL`
- `LINE_OFFICIAL_ACCOUNT_QR_URL`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`

Notes:

- `APP_BASE_URL` should point to the deployed domain.
- If `APP_BASE_URL` is entered without a scheme, the app will normalize it to `https://...`.
- SMTP is optional; Web Push and LINE can be tested without it.
- The scheduler service needs the same delivery-related env vars as the web service.

## Web Push Notes

- Uses standard browser Web Push, not native mobile APNs app code
- Requires:
  - browser notification permission
  - service worker registration
  - VAPID keys
  - HTTPS in production
- Notification clicks open a tracking URL, not a plain dashboard link

## LINE Notes

### Linking flow

1. Agent chooses `LINE` in Preferences.
2. Agent adds the LINE Official Account as a friend.
3. Agent sends a one-time link code to the OA.
4. `POST /line/webhook` receives the event.
5. App links `LINE userId` to the logged-in agent.
6. App replies in LINE confirming successful linking.

### Webhook endpoint

- `POST /line/webhook`

## Tracking and Conversion

Each dispatch gets:

- `tracking_token`
- `scheduled_dispatch_time`
- `status`
- `opened_timestamp`

Tracking endpoint:

- `GET /track/{tracking_token}`

Behavior:

- clicking a push / LINE / email tracking link marks `opened_timestamp`
- admin dashboard surfaces:
  - successful conversions
  - open rate
  - recent conversion rows

## Test Reset Utilities

For repeated demos on production, use:

- [scripts/reset_test_state.py](/Users/sungmin/Desktop/Project/kaggle-housing-price-prediction/kgi-mini-project/scripts/reset_test_state.py)

Examples:

Reset today's dispatches only:

```bash
railway run python scripts/reset_test_state.py --email lin.agent@smartnudge.example
```

Reset LINE app-side linking state:

```bash
railway run python scripts/reset_test_state.py --email lin.agent@smartnudge.example --reset-line
```

Reset push subscriptions:

```bash
railway run python scripts/reset_test_state.py --email lin.agent@smartnudge.example --reset-push
```

Reset assignment completion back to pending:

```bash
railway run python scripts/reset_test_state.py --email lin.agent@smartnudge.example --reset-assignments
```

## Recommended Demo Scenarios

1. **Agent onboarding**
   - login
   - open preferences
   - choose channel
   - save DND / peak time

2. **Web Push**
   - enable push
   - run scheduler
   - receive push
   - click push
   - verify `opened` in admin

3. **LINE**
   - choose LINE
   - add OA friend
   - send link code
   - run scheduler
   - receive LINE message
   - click tracking link
   - verify conversion in admin

4. **DND block**
   - set DND to include current time
   - run scheduler
   - verify nothing is sent

5. **Channel change re-send**
   - send with one channel
   - switch channel
   - run scheduler again
   - verify delivery uses the new channel

## Current Scope

This project intentionally treats:

- assignment due dates
- peak learning time

as upstream inputs.

It does **not** implement the reinforcement-learning algorithm itself.  
It implements the notification engine that acts on those inputs.
