# my_cruise frontend

React + Vite + Tailwind frontend for the my_cruise Phase 1 Traveler/Admin and Phase 2 Partner/Partner Website platform.

## Included workflows

### Traveler
- Sign up, login, email OTP verification and password reset
- Cruise discovery, search, date/guest/price filters
- Cruise details, itinerary, cabin types, amenities and live sailing availability
- Saved cruises
- Multi-step cabin booking and guest details
- USD Stripe checkout UI
- Booking confirmation, e-ticket and booking status
- Cancellation/refund preview and cancellation request
- Booking/refund notifications and browser push registration
- Partner application

### Admin
- Dashboard and operational resources
- Cruise, ship, port, amenity, sailing and inventory management
- Traveler booking visibility and booking details
- Cancellation approval/rejection and refund handling
- Refund policy/rule management
- Partner application approval/rejection
- Partner agency status management
- Partner cruise approval/rejection and commission configuration
- Partner website activation/suspension
- Website-specific cruise exposure
- Partner API key issue/revoke

### Partner
- Partner dashboard
- Cruise create/edit/delete and approval workflow
- Ship/deck/cabin type/cabin/amenity setup
- Cruise images and itinerary
- Sailing creation
- Central inventory availability/price/block management
- Partner booking visibility and commission
- Partner website registration and integration status

## Local development

1. Copy `.env.example` to `.env` and configure the values you need.
2. Start the FastAPI backend.
3. Install dependencies and start Vite:

```bash
npm install
npm run dev
```

Production build:

```bash
npm run build
```

The frontend uses `VITE_API_URL` for the API base URL. Stripe and Firebase values are optional for local UI work, but real Stripe checkout and browser push require their respective credentials.
