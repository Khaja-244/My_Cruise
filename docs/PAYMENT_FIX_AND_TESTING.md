# Stripe Payment Flow - Beginner Guide

## What the checkout does

1. Traveler signs in.
2. Traveler selects a cabin and submits guest details.
3. Backend creates a temporary cabin hold.
4. Backend creates one Stripe PaymentIntent for the booking total.
5. Frontend displays Stripe Payment Element with **card only** in Phase 1.
6. The browser validates the Payment Element with `elements.submit()`.
7. Stripe confirms the PaymentIntent.
8. Stripe sends `payment_intent.succeeded` to `/api/webhooks/stripe`.
9. Backend verifies the Stripe signature and amount/currency.
10. Backend changes the booking to `confirmed` and inventory to `booked`.
11. The ticket service generates the e-ticket after confirmation.

## Local test

### Backend

```powershell
cd backend
.venv\Scripts\activate
uvicorn app.main:app --reload
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

### Stripe webhook

```powershell
stripe listen --forward-to localhost:8000/api/webhooks/stripe
```

Copy the webhook signing secret printed by Stripe CLI into `backend/.env` as `STRIPE_WEBHOOK_SECRET`.

## Test card

Use Stripe's test card:

- Number: `4242 4242 4242 4242`
- Expiry: any future date
- CVC: any 3 digits
- ZIP: any valid value

## If the browser says CORS

The API allows local Vite ports 5173 and 5174. CORS is registered as the outermost middleware so authentication errors still contain CORS headers. This makes the real API error visible in DevTools.

## If payment says `Unable to start payment`

Check these in order:

1. You are logged in.
2. Backend is running on port 8000.
3. `backend/.env` contains a valid Stripe test secret key.
4. `frontend/.env` contains the matching Stripe test publishable key.
5. The booking is still within its 10-minute cabin hold.
6. Stripe CLI is running if webhook confirmation is being tested locally.

Do not mark a booking as confirmed from the frontend. The Stripe webhook is the server-side source of truth.
