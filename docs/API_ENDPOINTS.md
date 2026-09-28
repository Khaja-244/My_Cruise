# Phase 1 API Endpoint Catalog

Base URL: `/api`

These are the canonical Phase 1 endpoint paths. Docker is intentionally deferred.

## Public / Authentication

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/auth/register` | Register traveler |
| POST | `/auth/login` | Login traveler/admin |
| POST | `/auth/refresh` | Rotate refresh token |
| POST | `/auth/logout` | Logout |
| GET | `/auth/me` | Current user |
| POST | `/auth/forgot-password` | Send password-reset OTP |
| POST | `/auth/verify-otp` | Verify password-reset OTP |
| POST | `/auth/resend-otp` | Resend OTP |
| POST | `/auth/reset-password` | Reset password |
| PATCH | `/auth/me` | Update profile |
| POST | `/auth/change-password` | Change password |
| POST | `/auth/verify-email` | Verify email OTP |

## Cruise Discovery

| GET | `/cruises` | Search/filter cruises |
| GET | `/cruises/featured` | Most-booked cruises |
| GET | `/cruises/{slug}` | Cruise detail |
| GET | `/cruises/{slug}/sailings` | Open sailings |
| GET | `/sailings/{sailing_id}/availability` | Live cabin availability |
| GET | `/ports` | Public ports |
| GET | `/amenities` | Public amenities |

## Traveler

| GET | `/saved-cruises` | Saved cruises |
| POST | `/saved-cruises` | Save cruise |
| DELETE | `/saved-cruises/{id}` | Remove saved cruise |
| POST | `/bookings/hold` | Hold selected cabins |
| GET | `/bookings` | My bookings |
| GET | `/bookings/{reference}` | Booking detail |
| GET | `/bookings/{reference}/ticket` | E-ticket |
| POST | `/bookings/{reference}/cancel-request` | Request cancellation |
| GET | `/bookings/{reference}/refund-preview` | Refund preview |
| POST | `/payments/intent` | Create Stripe PaymentIntent |
| GET | `/payments/{booking_reference}/status` | Payment status |
| GET | `/notifications` | Notifications |
| PATCH | `/notifications/{id}/read` | Mark notification read |
| PATCH | `/notifications/read-all` | Mark all notifications read |
| GET | `/notifications/unread-count` | Unread count |
| POST | `/devices/token` | Register FCM token |
| DELETE | `/devices/token` | Remove FCM token |

## Stripe Webhook

| POST | `/webhooks/stripe` | Stripe event receiver |

## Admin

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/admin/dashboard/stats` | Dashboard statistics |
| GET/POST/PATCH/DELETE | `/admin/ships` / `/admin/ships/{id}` | Ship management |
| GET/POST/PATCH/DELETE | `/admin/ports` / `/admin/ports/{id}` | Port management |
| GET/POST/PATCH/DELETE | `/admin/cruises` / `/admin/cruises/{id}` | Cruise management |
| POST | `/admin/cruises/{id}/publish` | Publish cruise |
| POST | `/admin/cruises/{id}/archive` | Archive cruise |
| POST | `/admin/cruises/{id}/images/presign` | Presign image upload |
| POST | `/admin/cruises/{id}/images` | Save cruise image |
| PUT | `/admin/cruises/{id}/itinerary` | Replace itinerary |
| GET/POST | `/admin/cruises/{id}/cabin-types` | List/create cabin types |
| PATCH/DELETE | `/admin/cruises/{id}/cabin-types/{ct_id}` | Update/delete cabin type |
| PUT | `/admin/cruises/{id}/cabin-types/{ct_id}/amenities` | Replace amenities |
| POST | `/admin/ships/{id}/decks` | Create deck |
| POST | `/admin/ships/{id}/cabins` | Bulk-create cabins |
| GET/POST | `/admin/sailings` | List/create sailings |
| PATCH | `/admin/sailings/{id}` | Update sailing |
| GET | `/admin/sailings/{id}/inventory` | Inventory grid |
| PATCH | `/admin/sailings/{id}/cabins/{cabin_id}/block` | Block/unblock cabin |
| POST | `/admin/sailings/{id}/cancel` | Operator cancellation |
| GET | `/admin/bookings` | Admin booking list |
| GET | `/admin/bookings/{reference}` | Admin booking detail |
| GET | `/admin/cancellation-requests` | Cancellation queue |
| GET | `/admin/cancellation-requests/{id}` | Cancellation detail |
| POST | `/admin/cancellation-requests/{id}/approve` | Approve cancellation |
| POST | `/admin/cancellation-requests/{id}/reject` | Reject cancellation |
| GET/POST | `/admin/refund-policies` | Refund policy management |
| PUT | `/admin/refund-policies/{id}/rules` | Replace policy rules |
| GET/POST | `/admin/users` | List/create users |
| PATCH | `/admin/users/{id}/status` | Activate/deactivate user |
| GET | `/admin/audit-logs` | Audit log |

## Health

- GET `/health` — liveness
- GET `/health/ready` — database/Redis readiness

## Phase 2 Partner API
- `POST /api/partners/applications` — traveler partner application
- `GET /api/partners/application/me` — current application
- `GET /api/partners/dashboard` — partner dashboard
- `POST /api/partners/cruises` — submit owned cruise
- `GET /api/partners/cruises/{cruise_id}` — get owned cruise details
- `DELETE /api/partners/cruises/{cruise_id}` — remove pending cruise
- `GET /api/partners/applications` — admin application queue
- `POST /api/partners/applications/{application_id}/review` — approve/reject application
- `POST /api/partners` — directly onboard a partner agency (admin)
- `GET /api/partners/cruises/pending` — admin cruise review queue
- `POST /api/partners/cruises/{cruise_id}/review` — approve/reject partner cruise
- `POST /api/partners/api-keys` — issue partner API key (admin)
- `POST /api/partners/api-keys/{key_id}/revoke` — revoke API key (admin)
- `GET /api/partner-api/cruises` — API-key catalog
- `GET /api/partner-api/cruises/{cruise_id}/sailings`
- `GET /api/partner-api/sailings/{sailing_id}/availability` — central inventory availability
- `GET /api/partners/list` — admin partner list
- `PATCH /api/partners/{partner_id}/status` — enable/disable partner
- `PATCH /api/partners/cruises/{cruise_id}/commission` — set percent/flat commission
- `POST /api/partners/websites` — register partner website
- `POST /api/partner-api/bookings` — create a central-inventory booking hold
- `GET /api/partner-api/bookings/{reference}` — partner booking status
- `POST /api/partner-api/bookings/{reference}/payment-intent` — create/reuse payment intent
- `GET /api/partner-api/bookings/{reference}/payment-status` — latest payment/booking state
- `GET /api/partner-api/bookings/{reference}/ticket` — download confirmed e-ticket
- `POST /api/partner-api/bookings/{reference}/cancel-request` — request cancellation

## Phase 2 completion endpoints

### Traveler partner onboarding
- `POST /api/partners/applications` — submit partner application
- `GET /api/partners/application/me` — current application status

### Partner dashboard
- `GET /api/partners/dashboard`
- `POST /api/partners/cruises`
- `GET/PATCH/DELETE /api/partners/cruises/{cruise_id}`
- `POST /api/partners/cruises/{cruise_id}/decks`
- `POST /api/partners/cruises/{cruise_id}/cabin-types`
- `POST /api/partners/cruises/{cruise_id}/cabins`
- `POST /api/partners/cruises/{cruise_id}/images`
- `POST /api/partners/cruises/{cruise_id}/images/presign`
- `PUT /api/partners/cruises/{cruise_id}/itinerary`
- `POST /api/partners/cruises/{cruise_id}/sailings`
- `GET/POST /api/partners/websites`

### Admin partner operations
- `GET /api/partners/applications`
- `POST /api/partners/applications/{application_id}/review`
- `GET /api/partners/cruises/pending`
- `POST /api/partners/cruises/{cruise_id}/review`
- `PATCH /api/partners/cruises/{cruise_id}/commission`
- `GET /api/partners/list`
- `PATCH /api/partners/{partner_id}/status`
- `GET /api/partners/{partner_id}/exposures`
- `PUT /api/partners/{partner_id}/exposures/{cruise_id}`
- `GET /api/partners/{partner_id}/api-keys`
- `POST /api/partners/api-keys`
- `POST /api/partners/api-keys/{key_id}/revoke`
- `GET /api/partners/websites/admin`
- `PATCH /api/partners/websites/{website_id}/status`

### Partner API-key API
Authenticate with `X-Partner-API-Key`; this API is separate from traveler JWT auth.
- `GET /api/partner-api/cruises`
- `GET /api/partner-api/cruises/{cruise_id}/sailings`
- `GET /api/partner-api/sailings/{sailing_id}/availability`
- `POST /api/partner-api/bookings`
- `GET /api/partner-api/bookings/{reference}`
- `POST /api/partner-api/bookings/{reference}/cancel-request`

Partner API bookings use the same `cabin_inventory` row lock and booking service as direct traveler holds.


### Partner payments and tickets
- `POST /api/partner-api/bookings/{reference}/payment-intent` — create/reuse a Stripe PaymentIntent for a partner booking; authenticated with `X-Partner-API-Key`.
- `GET /api/partner-api/bookings/{reference}/ticket` — download the confirmed partner booking e-ticket PDF; authenticated with `X-Partner-API-Key`.
- `POST /api/partners` — admin-only direct partner-agency onboarding; generates and emails a temporary password.

### Availability response pricing fields

`GET /api/sailings/{sailing_id}/availability` also returns:

- `port_fee_per_guest_cents` — port fee used for the booking estimate.
- `tax_rate` — current configured tax rate used for the booking estimate.

The booking hold endpoint remains the final pricing authority and recalculates the amount server-side.
