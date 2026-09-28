# My Cruise

A full-stack cruise booking platform for travelers, administrators, approved partners, and partner websites.

My Cruise provides a centralized cruise booking system where travelers can search and book cruises, administrators can manage the platform, and approved partners can manage cruises and connect their own websites through APIs.

---

## Project Phases

### Phase 1 – Traveler & Admin

#### Traveler Side

- Sign up and login
- Forgot password with email OTP verification
- Landing page with cruise information
- Header and footer
- Saved cruises
- Browse available cruises
- Select preferred cruise
- Select sailing date
- View cruise details
- View ship information
- View embarkation and return ports
- View sailing information
- View decks and cabins
- View cabin amenities
- View real cabin availability
- Select cabin
- Select guest/occupancy details
- Create a booking
- Temporarily hold selected cabin inventory
- Stripe payment
- Booking confirmation
- E-ticket generation
- View booking history
- View booking details
- Cancel booking
- Refund workflow
- Notifications
- Traveler profile management

#### Admin Side

- Admin login
- Admin dashboard
- User management
- Cruise management
- Ship management
- Port management
- Deck management
- Cabin type management
- Cabin management
- Sailing management
- Inventory management
- Booking management
- View traveler booking details
- Cancellation management
- Refund management
- Dashboard statistics
- Audit logs
- Notification management

---

# Phase 2 – Partner & Partner Website Integration

## Partner Application

- Traveler can apply to become a partner
- Admin can view partner applications
- Admin can approve partner applications
- Admin can reject partner applications
- Approved partners receive partner access
- Partner dashboard
- Partner account management

## Partner Cruise Management

Approved partners can manage their cruises through the partner dashboard.

Features include:

- Add cruise
- Edit cruise
- Delete cruise
- Configure cruise name
- Configure ship
- Configure embarkation port
- Configure return port
- Configure sailing days
- Configure start and return dates
- Configure decks
- Configure deck names
- Configure cabin types
- Configure cabin capacity
- Configure cabin amenities
- Configure physical cabins
- Manage cabin availability
- Upload cruise images
- Configure itinerary
- Configure sailings
- Submit cruises to Admin for review

## Admin Partner Management

Administrators can manage approved partners and partner content.

Features include:

- View partner agencies
- Activate partner
- Deactivate partner
- Review partner cruises
- Approve partner cruises
- Reject partner cruises
- Configure partner commission
- Manage partner websites
- Manage partner API credentials
- Manage partner integrations
- View partner bookings

## Partner Website Integration

Approved partner websites can connect with My Cruise through the Partner API.

Partner API capabilities include:

- Retrieve approved cruises
- Retrieve cruise details
- Retrieve sailing information
- Retrieve cabin availability
- Create partner bookings
- Retrieve partner booking details
- Synchronize booking information
- Synchronize inventory availability
- Support cancellation workflows

---

# Central Inventory

My Cruise uses centralized cabin inventory for direct traveler bookings and partner website bookings.

The same inventory system is used across sales channels.

```text
                    My Cruise
                       |
             Central Cabin Inventory
                       |
          +------------+------------+
          |                         |
    Direct Traveler          Partner Website
       Booking                   Booking
          |                         |
          +------------+------------+
                       |
                 Same Inventory