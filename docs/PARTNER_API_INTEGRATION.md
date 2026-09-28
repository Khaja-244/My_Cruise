# Partner API Integration Guide

Base URL:

```text
https://<my-cruise-host>/api/partner-api
```

Authentication uses the `X-Partner-API-Key` header. The API key must belong to an active partner whose integration status is `connected`.

## 1. List exposed cruises

```http
GET /cruises
X-Partner-API-Key: <key>
```

Only approved, published cruises with enabled partner exposure are returned.

## 2. List sailings

```http
GET /cruises/{cruise_id}/sailings
X-Partner-API-Key: <key>
```

## 3. Check central inventory

```http
GET /sailings/{sailing_id}/availability
X-Partner-API-Key: <key>
```

The response is read from the same central `cabin_inventory` table used by my_cruise and other partner channels.

## 4. Create a booking hold

```http
POST /bookings
X-Partner-API-Key: <key>
Idempotency-Key: <unique-key>
Content-Type: application/json
```

Example:

```json
{
  "sailing_id": "<uuid>",
  "cabins": [
    {"cabin_id": "<uuid>", "occupancy": 2}
  ],
  "guest_count": 2,
  "customer_name": "Test Customer",
  "customer_email": "customer@example.com",
  "customer_phone": "9999999999",
  "guests": [
    {
      "cabin_id": "<uuid>",
      "full_name": "Test Customer",
      "date_of_birth": "1990-01-01",
      "nationality": "IN",
      "is_lead_guest": true
    }
  ]
}
```

A simultaneous booking attempt against the same cabin is serialized by PostgreSQL row locking. The first successful claim receives HTTP 200; the competing claim receives HTTP 409.

## 5. Create Stripe PaymentIntent

```http
POST /bookings/{reference}/payment-intent
X-Partner-API-Key: <key>
```

The PaymentIntent is created in USD and contains the booking reference in Stripe metadata.

## 6. Booking status

```http
GET /bookings/{reference}
X-Partner-API-Key: <key>
```

## 7. Ticket

```http
GET /bookings/{reference}/ticket
X-Partner-API-Key: <key>
```

## 8. Cancellation

```http
POST /bookings/{reference}/cancel-request
X-Partner-API-Key: <key>
```

The request enters the same centralized cancellation/refund workflow used by direct traveler bookings.

## Central inventory rule

Partner websites must never maintain a separate source of truth for cabin availability. Every availability, booking and cancellation operation must use the my_cruise central inventory API.
## Website-scoped cruise exposure

A partner may have more than one connected website. Admin can expose a cruise independently per website.

For a website-specific integration, send both headers on Partner API requests:

- `X-Partner-API-Key: <partner API key>`
- `X-Partner-Website-ID: <connected partner website UUID>`

The website ID must belong to the partner and its integration must be `connected`. The `/cruises`, `/cruises/{cruise_id}/sailings`, availability, and booking flow all enforce the same website-scoped exposure.

Existing partner API clients that do not send `X-Partner-Website-ID` continue to use the legacy partner-level exposure records.

