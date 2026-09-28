# my_cruise — Phase 1

A production-oriented cruise booking platform with Traveler + Admin functionality.

## Stack
- FastAPI + Python 3.11+
- SQLAlchemy 2 async + Alembic
- PostgreSQL 15+
- React 18 + Vite + Tailwind
- Stripe PaymentIntents/Webhooks
- SMTP, FCM, Redis/S3 integration points

## Local setup (Docker intentionally deferred)
1. Create PostgreSQL database `my_cruise` and user `cruise`.
2. Copy `backend/.env.example` to `backend/.env` and set `DATABASE_URL` and `JWT_SECRET_KEY`.
3. `cd backend && python -m venv .venv && .venv\\Scripts\\activate` (Windows) or `source .venv/bin/activate` (Linux/macOS).
4. `pip install -r requirements.txt`
5. `alembic upgrade head`
6. `python seeds/seed.py`
7. `uvicorn app.main:app --reload --port 8000`
8. In another terminal: `cd frontend && npm install && npm run dev`

API docs: http://localhost:8000/docs
Frontend: http://localhost:5173

## Seed accounts
- Admin: value of `ADMIN_EMAIL` / `ADMIN_INITIAL_PASSWORD`
- Travelers: traveler1@example.com, traveler2@example.com, traveler3@example.com / `Traveler1234`

Change the initial admin password before any real deployment.

## Booking correctness
Cabin holds use a single PostgreSQL transaction, lock the sailing and requested inventory rows in deterministic order, recompute prices on the server, and require an Idempotency-Key. Stripe webhooks—not frontend success callbacks—confirm bookings.

## Docker
Docker Compose/Dockerfile integration is intentionally left for the later infrastructure step, as requested. The application itself does not depend on Docker-specific behavior.

## Tests
`pytest -q`

A PostgreSQL integration test should run the mandatory 20-client same-cabin concurrency scenario from the project brief before release.


## Security requirements

Before deployment, set `JWT_SECRET_KEY` to a cryptographically random secret (do not use `change-me`) and set `ADMIN_INITIAL_PASSWORD` to a unique strong temporary password. The application requires both values; there are no insecure production defaults.

If Firebase push notifications are enabled, provide the service-account JSON through your deployment secret manager and set `FIREBASE_CREDENTIALS_JSON` to the mounted secret path. Never commit or package the service-account JSON.
