# Starter Data

The local seed script creates a realistic starter catalog so the application can be reviewed without entering every record manually.

Run from the `backend` directory:

```bash
python -m seeds.seed
```

## Local accounts

| Account | Email | Password | Purpose |
|---|---|---|---|
| Admin | `admin123@mycruise.demo` | `DemoAdmin@12345` | Manage cruises, ships, bookings, refunds and partners |
| Partner | `partner123@mycruise.demo` | `DemoPartner@12345` | Manage partner cruises, shared inventory and website integration |
| Traveler 1 | `traveler123@mycruise.demo` | `DemoTraveler@12345` | Confirmed booking |
| Traveler 2 | `traveler456@mycruise.demo` | `DemoTraveler@12345` | Refunded booking |
| Traveler 3 | `traveler789@mycruise.demo` | `DemoTraveler@12345` | Pending cancellation |
| Traveler 4 | `traveler999@mycruise.demo` | `DemoTraveler@12345` | Saved cruises |

These accounts are for local development only. Do not use them in production.

## Catalog

The starter catalog includes:

- Caribbean Sunset Escape
- Mediterranean Discovery
- Gulf Horizon Voyage
- Greek Isles Escape
- Dubai & Arabian Sea Journey
- Azure Coast Escape through the approved partner channel

Each cruise has realistic ship, route, sailing, cabin type, cabin image and availability data.

## Cabin structure

Each ship has three decks with six physical cabins per deck.

Cabin types include:

- Interior
- Ocean View
- Balcony

A cabin is a passenger room/accommodation on the ship. Its occupancy value is the maximum number of passengers allowed in that room.
