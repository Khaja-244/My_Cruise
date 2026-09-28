# my_cruise — Final Manual QA Checklist

This checklist is based on the Phase 1 / Phase 2 requirements supplied for the project. The frontend follows the existing FastAPI endpoints and response models; the backend remains the source of truth for prices, inventory, booking status, payments, refunds and commissions.

## Phase 1 — Traveler

- [ ] Register a traveler account.
- [ ] Verify email with OTP.
- [ ] Log in / log out.
- [ ] Forgot password → OTP → reset password.
- [ ] Landing page hero and real cruise photo load clearly.
- [ ] Search cruises by destination/name, month and guests.
- [ ] Newly published cruises appear on the public cruise list without frontend data changes.
- [ ] Open cruise detail and verify ship, ports, duration, itinerary and cabin types.
- [ ] Select a sailing.
- [ ] Expand Deck 1, Deck 2 and Deck 3.
- [ ] Verify actual cabin numbers are displayed.
- [ ] Verify AVAILABLE / HELD / BOOKED / BLOCKED status is shown correctly.
- [ ] Verify held/booked cabins cannot be selected.
- [ ] Select an available cabin and enter the booking wizard.
- [ ] Confirm the selected cabin is preselected in Step 1.
- [ ] Set occupancy within the backend-provided maximum.
- [ ] Enter guest details.
- [ ] Review USD total.
- [ ] Secure cabin / booking hold.
- [ ] Verify hold countdown.
- [ ] Complete Stripe payment with configured Stripe credentials.
- [ ] Verify server-confirmed booking status.
- [ ] Verify e-ticket / booking detail.
- [ ] Verify booking notification.
- [ ] Request cancellation on a confirmed booking.
- [ ] Verify refund preview uses the backend refund policy.
- [ ] Verify admin approval/rejection workflow.
- [ ] Verify Stripe refund and traveler notification when Stripe is configured.
- [ ] Verify saved cruise add/remove.
- [ ] Verify notifications list, mark-read and mark-all-read.
- [ ] Verify profile update and password change.

## Phase 1 — Admin

- [ ] Dashboard revenue/bookings/pending-cancellation metrics load.
- [ ] Manage cruises.
- [ ] Manage ships, decks and cabins.
- [ ] Manage ports and amenities.
- [ ] Manage sailings.
- [ ] View bookings and booking details.
- [ ] Review cancellation requests.
- [ ] Approve/reject cancellation requests.
- [ ] Manage refund policies and rules.
- [ ] Verify USD refund values.
- [ ] Verify inventory status and booking status.
- [ ] Verify newly approved/published cruises appear to travelers.

## Phase 2 — Partner application

- [ ] Traveler submits partner application.
- [ ] Admin reviews application.
- [ ] Admin approves/rejects application.
- [ ] Approved partner receives credentials through configured email service.
- [ ] Partner can log in.
- [ ] Disabled partner cannot use the partner account until re-enabled.

## Phase 2 — Partner cruise management

- [ ] Create cruise.
- [ ] Edit cruise.
- [ ] Delete cruise when backend allows it.
- [ ] Set cruise name/slug/description.
- [ ] Configure ship and ports.
- [ ] Set sailing days/start date/return date.
- [ ] Add/edit/delete decks.
- [ ] Add/edit/delete cabin types.
- [ ] Add/edit/delete physical cabins.
- [ ] Set occupancy and amenities.
- [ ] Add/edit/delete cruise images.
- [ ] Set a cover image.
- [ ] Save itinerary.
- [ ] Add/edit/delete sailings.
- [ ] Verify sailing creation generates central inventory rows.
- [ ] Submit cruise for admin approval.

## Phase 2 — Admin partner operations

- [ ] Review partner cruises.
- [ ] Configure percentage commission.
- [ ] Configure flat USD commission.
- [ ] Approve/reject partner cruises.
- [ ] Add/enable/disable partner agencies.
- [ ] Issue/revoke partner API keys.
- [ ] Register/manage partner websites.
- [ ] Activate/suspend website integration.
- [ ] Enable/disable cruise exposure per partner website.

## Central inventory / anti-double-booking

- [ ] Create the same sailing/cabin inventory used by direct and partner channels.
- [ ] Book Cabin A101 from my_cruise.
- [ ] Refresh partner inventory and confirm A101 is BOOKED.
- [ ] Confirm admin inventory shows A101 as BOOKED.
- [ ] Attempt to book A101 from another channel and verify the backend rejects it.
- [ ] Hold a cabin from one channel and verify another channel cannot book it.
- [ ] Cancel/refund and verify inventory changes according to the backend workflow.
- [ ] Verify partner inventory editing cannot change HELD/BOOKED cabins.

## Production readiness checks

- [ ] Do not distribute a real `backend/.env` file.
- [ ] Configure local secrets from `backend/.env.example`.
- [ ] Configure `VITE_STRIPE_PUBLISHABLE_KEY` for Stripe UI.
- [ ] Configure Stripe secret/webhook values in backend.
- [ ] Configure Firebase credentials if push notifications are enabled.
- [ ] Configure object storage if partner image presigning/upload is enabled.
- [ ] Run `alembic upgrade head`.
- [ ] Run frontend `npm install` and `npm run build` locally.
- [ ] Run backend with Uvicorn and verify `/docs`.
