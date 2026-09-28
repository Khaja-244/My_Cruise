# Demo Data

Run the seed from the `backend` directory:

```cmd
python -m seeds.seed
```

The seed is idempotent and is intended for local/reviewer environments only.

## Demo credentials

| Role | Email | Password | What to review |
|---|---|---|---|
| Admin | `admin123@mycruise.demo` | `DemoAdmin@12345` | Dashboard, cruises, bookings, cancellations, refund policies, partner approval |
| Approved Partner | `partner123@mycruise.demo` | `DemoPartner@12345` | Partner dashboard, approved/pending/rejected cruises, inventory, website, API key |
| Traveler 1 | `traveler123@mycruise.demo` | `DemoTraveler@12345` | Confirmed booking `MCDEMO001` |
| Traveler 2 | `traveler456@mycruise.demo` | `DemoTraveler@12345` | Refunded booking `MCDEMO002` |
| Traveler 3 | `traveler789@mycruise.demo` | `DemoTraveler@12345` | Pending cancellation request `MCDEMO003` |
| Traveler 4 | `traveler999@mycruise.demo` | `DemoTraveler@12345` | Two saved cruises |
| Pending Partner applicant | `partnerpending123@mycruise.demo` | `DemoPartner@12345` | Pending application |
| Rejected Partner applicant | `partnerrejected123@mycruise.demo` | `DemoPartner@12345` | Rejected application |

## Partner integration demo key

The active demo partner has one active API key:

```text
mc_demo_partner_api_2026
```

Use it only for local/demo testing with the `X-Partner-API-Key` header. Never use this key in production.

## Demo dataset

The seed creates:

- 1 admin
- 4 travelers
- 3 partner accounts/applications: active, pending and rejected
- 1 connected partner website
- 1 active partner API key
- 6 cruises: 3 platform-owned and 3 partner-owned
- Partner cruises in pending, approved and rejected states
- 6 ships with 3 decks each
- 3 cabin types per demo cruise
- 18 physical cabins per demo ship
- Cabin amenities
- Itineraries
- Future scheduled/open sailings
- Central cabin inventory
- Confirmed, refunded/cancelled and cancellation-requested bookings
- Saved cruises
- Booking/refund/cancellation notifications
- Generic demo images using `picsum.photos`; these are placeholders and are not cruise-line/trademark images.

## Important

These credentials and API keys are demo-only. Change or remove them before any production deployment.
