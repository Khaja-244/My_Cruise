# my_cruise Architecture — Beginner View

This project is split into a small number of predictable layers. The goal is
that a beginner can follow one request from the browser to PostgreSQL without
needing to understand the whole application first.

## Folder map

```text
my_cruise/
├── backend/
│   ├── app/
│   │   ├── api/          # HTTP routes: receive requests and return responses
│   │   ├── core/         # authentication, settings, database and shared helpers
│   │   ├── models/       # SQLAlchemy database tables
│   │   ├── schemas/      # Pydantic request/response validation
│   │   ├── services/     # business rules and reusable workflows
│   │   └── tasks/        # background/scheduled jobs
│   ├── alembic/          # database migrations
│   ├── seeds/            # local demo data
│   └── tests/             # automated/unit/concurrency tests
├── frontend/
│   ├── src/api/          # shared Axios API client
│   ├── src/components/   # reusable UI pieces
│   ├── src/context/      # shared login/session state
│   ├── src/pages/        # screen-level React components
│   └── src/routes/       # protected/admin/partner route guards
└── docs/                 # project guides and QA documentation
```

## Booking request flow

```text
1. Traveler selects a cabin
       ↓
2. CabinDeckMap.jsx stores the real cabin_id
       ↓
3. BookingWizard.jsx sends POST /bookings/hold
       ↓
4. api/bookings.py validates the HTTP request
       ↓
5. services/booking_service.py applies booking rules
       ↓
6. services/inventory_service.py locks CabinInventory rows
       ↓
7. services/pricing_service.py calculates the server-side price
       ↓
8. SQLAlchemy commits the temporary hold
       ↓
9. Stripe PaymentIntent is created
       ↓
10. Stripe webhook confirms the booking
```

The frontend may show an estimated total, but the backend always calculates
the final amount again. The browser is never the source of truth for price or
inventory.

## Central inventory rule

There is one `CabinInventory` record for a cabin on a specific sailing.

Both of these paths use the same booking service:

- traveler → `POST /bookings/hold`
- partner website → `POST /partner-api/bookings`

The service locks the selected inventory rows before changing them. This is
what prevents the same cabin from being sold twice through different channels.

## How to read the code

For a first pass, read these files in this order:

1. `frontend/src/pages/traveler/BookingWizard.jsx`
2. `frontend/src/components/booking/CabinDeckMap.jsx`
3. `backend/app/api/bookings.py`
4. `backend/app/services/booking_service.py`
5. `backend/app/services/inventory_service.py`
6. `backend/app/services/pricing_service.py`
7. `backend/app/models/__init__.py`

Then read `backend/app/api/partner_api/bookings.py` to see how partner bookings
reuse the same central workflow.

## Important beginner rule

Keep responsibilities separated:

- React components display data and collect input.
- API routes handle HTTP concerns.
- Pydantic schemas validate request/response shapes.
- Services contain business rules.
- Models describe database tables.
- Migrations change database structure.

When adding a feature, start in the layer that owns that responsibility rather
than putting all logic into one large file.
