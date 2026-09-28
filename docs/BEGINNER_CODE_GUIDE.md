# Beginner-Friendly Code Guide

This project is intentionally organized so a new developer can trace one feature from the browser to the database.

## 1. Booking flow — start here

The cabin booking feature is the easiest place to understand the project:

```text
CruiseDetail.jsx
      ↓
BookingWizard.jsx
      ↓
CabinDeckMap.jsx
      ↓
GET /api/sailings/{sailing_id}/availability
      ↓
POST /api/bookings/hold
      ↓
booking_service.py
      ↓
CabinInventory rows in PostgreSQL
      ↓
Stripe payment + webhook
```

### Frontend files

- `frontend/src/pages/traveler/BookingWizard.jsx`
  - Controls the six booking steps.
  - Stores the selected cabin IDs and guest details.
  - Sends the final hold request to the backend.
- `frontend/src/components/booking/CabinDeckMap.jsx`
  - Only handles the visual deck plan.
  - It does **not** create or manage inventory.
  - A cabin click returns the same `cabin_id` already provided by the API.
- `frontend/src/api/client.js`
  - Shared Axios client.
  - Adds the access token and handles token refresh.

### Backend files

- `backend/app/api/cruises.py`
  - Reads live cabin inventory and groups it by deck and cabin type.
- `backend/app/api/bookings.py`
  - Exposes booking HTTP endpoints.
- `backend/app/services/booking_service.py`
  - Contains the important business rules for holding cabins.
  - Locks inventory before claiming it.
  - Uses the same function for direct and partner bookings.
- `backend/app/services/pricing_service.py`
  - Calculates subtotal, port fees, tax, and final total.
- `backend/app/models/__init__.py`
  - Defines database tables such as `CabinInventory`, `Booking`, and `BookingCabin`.

## 2. Why the cabin/deck map is safe

The deck map is only a visual layer. It never decides whether a cabin is really free.

When the traveler clicks a cabin:

1. React stores the cabin's real `cabin_id`.
2. The UI sends that ID to `POST /bookings/hold`.
3. The backend locks the corresponding inventory row.
4. If another website has already booked/held it, the backend rejects the request.
5. The UI refreshes availability after a conflict.

This is what keeps direct my_cruise bookings and partner-website bookings on one central inventory.

## 3. Frontend styling

The project uses Tailwind CSS plus the existing small design system in `frontend/src/index.css`.

Reusable classes include:

- `card`
- `btn btn-primary`
- `btn btn-outline`
- `btn btn-secondary`
- `muted`
- `eyebrow`
- `section-title`
- `status-pill`

The new deck plan uses Tailwind utilities and does not add a UI component library.

## 4. Real cruise photography

Demo cruise and cabin photography is centralized in:

`frontend/src/assets/images/photoSources.js`

The demo uses real photographic Unsplash/Pexels image URLs. Admin/API-provided cruise images still take precedence when available.

For production, replace those URLs with approved local/CDN assets.

## 5. Database changes for this UI update

No new migration is required for the visual deck plan.

The availability response now also exposes:

- `port_fee_per_guest_cents`
- `tax_rate`

These values let the frontend show a useful estimate before the booking hold. The backend still recalculates the final price inside the booking transaction.

## 6. Run locally

### Backend

```cmd
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
python -m seeds.seed
uvicorn app.main:app --reload
```

Swagger: `http://127.0.0.1:8000/docs`

### Frontend

Open a second terminal:

```cmd
cd frontend
npm install
npm run dev
```

Frontend: `http://localhost:5173`

## 7. Important rule for future changes

Do not put inventory or payment business rules inside React components. React should display state and collect input; the FastAPI service should validate and commit the booking.
