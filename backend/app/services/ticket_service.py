"""Professional e-ticket PDF generation and confirmation email delivery."""

import logging
from datetime import timezone
from decimal import Decimal
from io import BytesIO

from app.core.database import SessionLocal
from app.models import Cabin, CabinType, Payment
from app.services.email_service import send_email, wrap_email
from app.services.storage_service import put_bytes

log = logging.getLogger(__name__)

# my_cruise brand palette.
NAVY = "#101827"
NAVY_2 = "#172338"
TEAL = "#0B8277"
TEAL_DARK = "#075E58"
PURPLE = "#6D35C8"
TEXT = "#172033"
MUTED = "#667085"
LIGHT = "#F4F7FA"
LINE = "#D9E1E8"
WHITE = "#FFFFFF"
SUCCESS = "#0B7A5B"


def _money(cents: int) -> str:
    return f"${Decimal(cents or 0) / Decimal(100):,.2f}"


def _safe(value, fallback="—") -> str:
    if value is None or str(value).strip() == "":
        return fallback
    return str(value).strip()


def _date_text(value, fallback="—") -> str:
    if not value:
        return fallback
    if hasattr(value, "strftime"):
        return value.strftime("%d %b %Y")
    return str(value)


def _datetime_text(value, fallback="—") -> str:
    if not value:
        return fallback
    if hasattr(value, "astimezone"):
        try:
            return value.astimezone(timezone.utc).strftime("%d %b %Y, %H:%M UTC")
        except Exception:
            pass
    return str(value)


def _status_text(value) -> str:
    raw = getattr(value, "value", value)
    return str(raw or "").replace("_", " ").title() or "—"


def _load_font(canvas, bold=False, size=10):
    canvas.setFont("Helvetica-Bold" if bold else "Helvetica", size)


def _fit_text(canvas, text, max_width, size=9, bold=False):
    """Return text shortened to fit one PDF line."""
    text = _safe(text)
    font = "Helvetica-Bold" if bold else "Helvetica"
    canvas.setFont(font, size)
    if canvas.stringWidth(text, font, size) <= max_width:
        return text
    result = text
    while len(result) > 3 and canvas.stringWidth(result + "...", font, size) > max_width:
        result = result[:-1]
    return result + "..."


def _label_value(canvas, x, y, label, value, width, value_size=10):
    canvas.setFillColor(MUTED)
    _load_font(canvas, True, 7)
    canvas.drawString(x, y, label.upper())
    canvas.setFillColor(TEXT)
    _load_font(canvas, True, value_size)
    canvas.drawString(x, y - 15, _fit_text(canvas, value, width, value_size, True))


def _rounded_card(canvas, x, y, w, h, fill=LIGHT, stroke=LINE, radius=10):
    canvas.setFillColor(fill)
    canvas.setStrokeColor(stroke)
    canvas.setLineWidth(0.7)
    canvas.roundRect(x, y - h, w, h, radius, fill=1, stroke=1)


def _section(canvas, x, y, title, width):
    canvas.setFillColor(NAVY)
    _load_font(canvas, True, 9)
    canvas.drawString(x, y, title.upper())
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.7)
    canvas.line(x, y - 6, x + width, y - 6)
    return y - 25


def _draw_header(canvas, width, height, reference, qr_image):
    """Draw a clean airline-style e-ticket header."""
    header_y = height - 28
    canvas.setFillColor(NAVY)
    canvas.roundRect(32, header_y - 136, width - 64, 136, 16, fill=1, stroke=0)

    # Brand mark.
    canvas.setFillColor(TEAL)
    canvas.roundRect(50, header_y - 58, 42, 32, 9, fill=1, stroke=0)
    canvas.setFillColor(WHITE)
    _load_font(canvas, True, 17)
    canvas.drawCentredString(71, header_y - 47, "M")

    canvas.setFillColor(WHITE)
    _load_font(canvas, True, 19)
    canvas.drawString(105, header_y - 43, "my_cruise")
    canvas.setFillColor("#B8C5D2")
    _load_font(canvas, False, 7.5)
    canvas.drawString(106, header_y - 56, "SAIL BEAUTIFULLY")

    canvas.setFillColor("#AFC0D1")
    _load_font(canvas, True, 8)
    canvas.drawString(50, header_y - 82, "CRUISE E-TICKET")
    canvas.setFillColor(WHITE)
    _load_font(canvas, True, 22)
    canvas.drawString(50, header_y - 108, reference)
    canvas.setFillColor("#C7D2DE")
    _load_font(canvas, False, 7.5)
    canvas.drawString(50, header_y - 121, "Present this ticket and a valid passport at check-in.")

    canvas.drawImage(qr_image, width - 130, header_y - 119, 84, 84, preserveAspectRatio=True, mask="auto")
    canvas.setFillColor("#C7D2DE")
    _load_font(canvas, False, 6.5)
    canvas.drawCentredString(width - 88, header_y - 126, "SCAN AT CHECK-IN")


def _draw_route(canvas, x, y, width, from_port, to_port, departure, arrival):
    """Draw the prominent FROM/TO block required on every ticket."""
    h = 112
    _rounded_card(canvas, x, y, width, h, fill=WHITE, stroke=LINE)

    canvas.setFillColor(MUTED)
    _load_font(canvas, True, 7)
    canvas.drawString(x + 16, y - 18, "ROUTE")

    mid = x + width / 2
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(1)
    canvas.line(mid, y - 34, mid, y - h + 16)

    _label_value(canvas, x + 16, y - 40, "From", from_port, width / 2 - 34, 12)
    canvas.setFillColor(MUTED)
    _load_font(canvas, False, 7.5)
    canvas.drawString(x + 16, y - 72, f"Departure: {_date_text(departure)}")

    _label_value(canvas, mid + 16, y - 40, "To", to_port, width / 2 - 34, 12)
    canvas.setFillColor(MUTED)
    _load_font(canvas, False, 7.5)
    canvas.drawString(mid + 16, y - 72, f"Arrival / Return: {_date_text(arrival)}")


def _draw_passenger_card(canvas, x, y, width, guest, cabin_number):
    h = 112
    _rounded_card(canvas, x, y, width, h, fill="#F7F4FC", stroke="#E1D8F3")
    canvas.setFillColor(PURPLE)
    _load_font(canvas, True, 7)
    canvas.drawString(x + 16, y - 18, "PASSENGER")

    name = _safe(getattr(guest, "full_name", None))
    passport = _safe(getattr(guest, "passport_number", None))
    dob = _date_text(getattr(guest, "date_of_birth", None))
    nationality = _safe(getattr(guest, "nationality", None))

    canvas.setFillColor(NAVY)
    _load_font(canvas, True, 14)
    canvas.drawString(x + 16, y - 38, _fit_text(canvas, name, width - 32, 14, True))

    col = (width - 48) / 3
    _label_value(canvas, x + 16, y - 60, "Passport / ID", passport, col, 8.5)
    _label_value(canvas, x + 24 + col, y - 60, "Date of birth", dob, col, 8.5)
    _label_value(canvas, x + 32 + col * 2, y - 60, "Nationality", nationality, col - 8, 8.5)

    canvas.setFillColor(TEAL_DARK)
    _load_font(canvas, True, 8)
    canvas.drawString(x + 16, y - 96, f"CABIN {cabin_number}  •  {'LEAD GUEST' if getattr(guest, 'is_lead_guest', False) else 'GUEST'}")


def _draw_small_card(canvas, x, y, w, h, title, value, secondary=None):
    _rounded_card(canvas, x, y, w, h)
    canvas.setFillColor(MUTED)
    _load_font(canvas, True, 7)
    canvas.drawString(x + 12, y - 17, title.upper())
    canvas.setFillColor(TEXT)
    _load_font(canvas, True, 10)
    canvas.drawString(x + 12, y - 34, _fit_text(canvas, value, w - 24, 10, True))
    if secondary:
        canvas.setFillColor(MUTED)
        _load_font(canvas, False, 7.5)
        canvas.drawString(x + 12, y - 49, _fit_text(canvas, secondary, w - 24, 7.5, False))


async def _load_ticket_data(booking, cabins):
    from sqlalchemy import select

    cabin_map = {}
    type_map = {}
    payment = None

    async with SessionLocal() as lookup_session:
        cabin_ids = [c.cabin_id for c in cabins]
        if cabin_ids:
            rows = (await lookup_session.scalars(select(Cabin).where(Cabin.id.in_(cabin_ids)))).all()
            cabin_map = {row.id: row for row in rows}
            type_ids = [row.cabin_type_id for row in rows]
            if type_ids:
                type_rows = (await lookup_session.scalars(select(CabinType).where(CabinType.id.in_(type_ids)))).all()
                type_map = {row.id: row.name for row in type_rows}

        payment = await lookup_session.scalar(
            select(Payment).where(Payment.booking_id == booking.id).order_by(Payment.created_at.desc())
        )

    return cabin_map, type_map, payment


async def ticket_pdf(booking, guests, cabins, cruise, ship, sailing, embark_port=None, disembark_port=None):
    """Create a clean, one-page professional cruise e-ticket."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas
    import qrcode

    # These fields are required because they are printed on the official ticket.
    if not embark_port or not getattr(embark_port, "name", None):
        raise ValueError("The cruise embarkation port is required before generating the ticket.")
    if not disembark_port or not getattr(disembark_port, "name", None):
        raise ValueError("The cruise disembarkation port is required before generating the ticket.")
    if not guests:
        raise ValueError("At least one passenger is required before generating the ticket.")

    for guest in guests:
        if not _safe(getattr(guest, "full_name", None), "").strip():
            raise ValueError("Every passenger must have a full name.")
        if not getattr(guest, "date_of_birth", None):
            raise ValueError("Every passenger must have a date of birth.")
        if not _safe(getattr(guest, "passport_number", None), "").strip():
            raise ValueError("Every passenger must have a passport / ID number.")
        if not _safe(getattr(guest, "nationality", None), "").strip():
            raise ValueError("Every passenger must have a nationality.")

    cabin_map, type_map, payment = await _load_ticket_data(booking, cabins)

    # QR code contains the booking reference for quick terminal lookup.
    qr = qrcode.make(booking.booking_reference)
    qr_buffer = BytesIO()
    qr.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)
    qr_image = ImageReader(qr_buffer)

    width, height = A4
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=A4)
    pdf.setTitle(f"my_cruise E-Ticket - {booking.booking_reference}")
    pdf.setAuthor("my_cruise")
    pdf.setSubject("Cruise boarding e-ticket")

    cruise_name = _safe(getattr(cruise, "name", None), "Cruise")
    ship_name = _safe(getattr(ship, "name", None), "Cruise ship")
    from_port = _safe(getattr(embark_port, "name", None))
    to_port = _safe(getattr(disembark_port, "name", None))
    lead_guest = next((g for g in guests if getattr(g, "is_lead_guest", False)), guests[0])
    lead_cabin = cabin_map.get(getattr(lead_guest, "cabin_id", None))
    lead_cabin_number = getattr(lead_cabin, "cabin_number", "—") if lead_cabin else "—"
    lead_cabin_type = type_map.get(getattr(lead_cabin, "cabin_type_id", None), "Cabin") if lead_cabin else "Cabin"

    left = 42
    right = width - 42
    content_w = right - left

    # ---------- HEADER: dark premium boarding-pass style ----------
    header_h = 112
    header_top = height - 24
    header_bottom = header_top - header_h
    pdf.setFillColor(NAVY)
    pdf.roundRect(left, header_bottom, content_w, header_h, 14, fill=1, stroke=0)

    # Brand mark.
    pdf.setFillColor(TEAL)
    pdf.roundRect(left + 16, header_top - 48, 34, 30, 8, fill=1, stroke=0)
    pdf.setFillColor(WHITE)
    _load_font(pdf, True, 15)
    pdf.drawCentredString(left + 33, header_top - 38, "M")
    pdf.setFillColor(WHITE)
    _load_font(pdf, True, 17)
    pdf.drawString(left + 61, header_top - 33, "my_cruise")
    pdf.setFillColor("#B8C5D2")
    _load_font(pdf, False, 6.5)
    pdf.drawString(left + 62, header_top - 45, "SAIL BEAUTIFULLY")

    pdf.setFillColor("#AFC0D1")
    _load_font(pdf, True, 7)
    pdf.drawString(left + 16, header_top - 68, "CRUISE E-TICKET / BOARDING PASS")
    pdf.setFillColor(WHITE)
    _load_font(pdf, True, 18)
    pdf.drawString(left + 16, header_top - 91, booking.booking_reference)

    # Confirmation badge and issued date.
    badge_w = 82
    pdf.setFillColor("#DDF7EE")
    pdf.roundRect(right - badge_w - 16, header_top - 42, badge_w, 23, 8, fill=1, stroke=0)
    pdf.setFillColor(TEAL_DARK)
    _load_font(pdf, True, 7)
    pdf.drawCentredString(right - badge_w / 2 - 16, header_top - 34, "CONFIRMED")
    pdf.setFillColor("#C7D2DE")
    _load_font(pdf, False, 6.5)
    pdf.drawRightString(right - 16, header_top - 55, f"Issued {_date_text(getattr(booking, 'confirmed_at', None) or getattr(booking, 'created_at', None))}")

    # ---------- ROUTE ----------
    y = header_bottom - 16
    route_h = 72
    _rounded_card(pdf, left, y, content_w, route_h, fill=WHITE, stroke=LINE, radius=9)
    mid = left + content_w / 2
    pdf.setFillColor(MUTED)
    _load_font(pdf, True, 6.5)
    pdf.drawString(left + 14, y - 15, "FROM")
    pdf.drawRightString(right - 14, y - 15, "TO")
    pdf.setFillColor(TEXT)
    _load_font(pdf, True, 10.5)
    pdf.drawString(left + 14, y - 31, _fit_text(pdf, from_port, 145, 10.5, True))
    pdf.drawRightString(right - 14, y - 31, _fit_text(pdf, to_port, 145, 10.5, True))
    pdf.setFillColor(MUTED)
    _load_font(pdf, False, 6.8)
    pdf.drawString(left + 14, y - 47, f"Departure · {_date_text(getattr(sailing, 'departure_date', None))}")
    pdf.drawRightString(right - 14, y - 47, f"Arrival / Return · {_date_text(getattr(sailing, 'return_date', None))}")
    pdf.setStrokeColor(TEAL)
    pdf.setLineWidth(1.2)
    pdf.line(mid - 55, y - 38, mid + 55, y - 38)
    pdf.setFillColor(WHITE)
    pdf.setStrokeColor(TEAL)
    pdf.roundRect(mid - 28, y - 46, 56, 16, 7, fill=1, stroke=1)
    pdf.setFillColor(TEAL_DARK)
    _load_font(pdf, True, 6)
    nights = ""
    dep = getattr(sailing, "departure_date", None)
    ret = getattr(sailing, "return_date", None)
    try:
        nights = f"{(ret - dep).days} NIGHTS" if dep and ret else "CRUISE"
    except Exception:
        nights = "CRUISE"
    pdf.drawCentredString(mid, y - 40, nights)
    y -= route_h + 12

    # ---------- PASSENGER + BOOKING CARDS ----------
    card_gap = 10
    card_w = (content_w - card_gap) / 2
    card_h = 76
    _rounded_card(pdf, left, y, card_w, card_h, fill=WHITE, stroke=LINE, radius=8)
    pdf.setFillColor(TEAL)
    pdf.rect(left, y - card_h, 4, card_h, fill=1, stroke=0)
    pdf.setFillColor(MUTED)
    _load_font(pdf, True, 6.5)
    pdf.drawString(left + 14, y - 16, "PASSENGER")
    pdf.setFillColor(TEXT)
    _load_font(pdf, True, 11)
    pdf.drawString(left + 14, y - 32, _fit_text(pdf, _safe(getattr(lead_guest, "full_name", None)), card_w - 28, 11, True))
    pdf.setFillColor(MUTED)
    _load_font(pdf, False, 6.8)
    pdf.drawString(left + 14, y - 47, f"Passport / ID · {_safe(getattr(lead_guest, 'passport_number', None))}")
    pdf.drawString(left + 14, y - 59, f"DOB · {_date_text(getattr(lead_guest, 'date_of_birth', None))}   •   Nationality · {_safe(getattr(lead_guest, 'nationality', None))}")
    pdf.setFillColor(TEAL_DARK)
    _load_font(pdf, True, 6.5)
    pdf.drawString(left + 14, y - 70, f"CABIN {lead_cabin_number}  •  {'LEAD GUEST' if getattr(lead_guest, 'is_lead_guest', False) else 'GUEST'}")

    bx = left + card_w + card_gap
    _rounded_card(pdf, bx, y, card_w, card_h, fill=WHITE, stroke=LINE, radius=8)
    pdf.setFillColor(PURPLE)
    pdf.rect(bx, y - card_h, 4, card_h, fill=1, stroke=0)
    pdf.setFillColor(MUTED)
    _load_font(pdf, True, 6.5)
    pdf.drawString(bx + 14, y - 16, "BOOKING REFERENCE")
    pdf.setFillColor(TEXT)
    _load_font(pdf, True, 11)
    pdf.drawString(bx + 14, y - 32, booking.booking_reference)
    pdf.setFillColor(MUTED)
    _load_font(pdf, False, 6.8)
    pdf.drawString(bx + 14, y - 47, f"Cabin {lead_cabin_number} · {lead_cabin_type} · {len(guests)} guest(s)")
    pdf.drawString(bx + 14, y - 59, f"Cruise · {_fit_text(pdf, cruise_name, card_w - 28, 6.8, False)}")
    pdf.drawString(bx + 14, y - 70, f"Ship · {_fit_text(pdf, ship_name, card_w - 28, 6.8, False)}")
    y -= card_h + 12

    # ---------- BOARDING STUB + QR ----------
    stub_h = 78
    _rounded_card(pdf, left, y, content_w, stub_h, fill=LIGHT, stroke=LINE, radius=8)
    pdf.setFillColor(NAVY)
    _load_font(pdf, True, 7)
    pdf.drawString(left + 14, y - 17, "BOARDING STUB · PRESENT AT TERMINAL")
    pdf.setFillColor(TEXT)
    _load_font(pdf, True, 9.5)
    pdf.drawString(left + 14, y - 34, _fit_text(pdf, _safe(getattr(lead_guest, "full_name", None)), 260, 9.5, True))
    pdf.setFillColor(MUTED)
    _load_font(pdf, False, 7)
    pdf.drawString(left + 14, y - 48, f"Cabin {lead_cabin_number} · Booking {booking.booking_reference}")
    pdf.drawString(left + 14, y - 61, f"Sailing {_date_text(getattr(sailing, 'departure_date', None))} → {_date_text(getattr(sailing, 'return_date', None))}")
    pdf.drawImage(qr_image, right - 78, y - 70, 58, 58, preserveAspectRatio=True, mask="auto")
    pdf.setFillColor(MUTED)
    _load_font(pdf, False, 5.8)
    pdf.drawCentredString(right - 49, y - 72, "SCAN AT CHECK-IN")
    y -= stub_h + 12

    # ---------- CABIN / FARE SUMMARY ----------
    section_y = y
    pdf.setFillColor(NAVY)
    _load_font(pdf, True, 7.5)
    pdf.drawString(left, section_y, "CABIN & FARE SUMMARY")
    y -= 12
    row_h = 23
    _rounded_card(pdf, left, y, content_w, row_h, fill=NAVY, stroke=NAVY, radius=5)
    cols = [65, 150, 72, 95, content_w - 382]
    cursor = left
    pdf.setFillColor(WHITE)
    _load_font(pdf, True, 6.2)
    for label, cw in zip(["CABIN", "TYPE", "GUESTS", "PRICE", "TOTAL PAID"], cols):
        pdf.drawString(cursor + 7, y - 15, label)
        cursor += cw
    y -= row_h
    first = True
    for cabin in cabins:
        cabin_obj = cabin_map.get(cabin.cabin_id)
        number = getattr(cabin_obj, "cabin_number", str(cabin.cabin_id))
        type_name = type_map.get(getattr(cabin_obj, "cabin_type_id", None), "Cabin")
        row = [number, type_name, str(cabin.occupancy), _money(cabin.price_cents), ""]
        if first:
            row[-1] = f"{_money(booking.total_cents)} {booking.currency}"
            first = False
        _rounded_card(pdf, left, y, content_w, row_h, fill=WHITE if first else LIGHT, stroke=LINE, radius=0)
        cursor = left
        pdf.setFillColor(TEXT)
        _load_font(pdf, False, 6.8)
        for value, cw in zip(row, cols):
            pdf.drawString(cursor + 7, y - 15, _fit_text(pdf, value, cw - 12, 6.8, False))
            cursor += cw
        y -= row_h

    # Payment line and status.
    payment_status = _status_text(getattr(payment, "status", None)) if payment else _status_text(getattr(booking, "status", None))
    payment_reference = _safe(getattr(payment, "stripe_payment_intent_id", None), "Paid") if payment else "Paid"
    pdf.setFillColor(MUTED)
    _load_font(pdf, False, 6.7)
    pdf.drawString(left + 8, y - 14, f"Payment status · {payment_status}   •   Stripe reference · {payment_reference}")
    pdf.drawRightString(right - 8, y - 14, f"TOTAL · {_money(booking.total_cents)} {booking.currency}")
    y -= 28

    # ---------- CHECKLIST ----------
    checklist_h = 66
    pdf.setFillColor("#EAF7F4")
    pdf.setStrokeColor("#B8E1D8")
    pdf.roundRect(left, y - checklist_h, content_w, checklist_h, 9, fill=1, stroke=1)
    pdf.setFillColor(TEAL_DARK)
    _load_font(pdf, True, 7.2)
    pdf.drawString(left + 14, y - 17, "BOARDING CHECKLIST")
    pdf.setFillColor(TEXT)
    _load_font(pdf, False, 6.8)
    checklist = [
        "Carry this e-ticket and your original passport / travel document.",
        "Passenger name and passport / ID details must match the document presented at check-in.",
        "Arrive at the terminal at least 2 hours before the scheduled departure.",
    ]
    line_y = y - 32
    for item in checklist:
        pdf.drawString(left + 14, line_y, f"• {item}")
        line_y -= 11
    y -= checklist_h + 10

    # ---------- CLOSING MESSAGE: requested style ----------
    pdf.setStrokeColor(LINE)
    pdf.line(left, y, right, y)
    pdf.setFillColor(TEAL_DARK)
    _load_font(pdf, True, 11)
    pdf.drawCentredString(width / 2, y - 17, "Bon voyage & happy sailing!")
    pdf.setFillColor(MUTED)
    _load_font(pdf, False, 7.2)
    closing = f"We hope you have a wonderful stay aboard {ship_name}. Wishing you smooth seas and unforgettable memories, {_safe(getattr(lead_guest, 'full_name', None))}."
    pdf.drawCentredString(width / 2, y - 31, _fit_text(pdf, closing, content_w - 20, 7.2, False))

    pdf.setFillColor(MUTED)
    _load_font(pdf, False, 6.2)
    pdf.drawString(left, 22, f"{booking.booking_reference}   •   my_cruise · Computer-generated e-ticket, valid without signature")
    pdf.drawRightString(right, 22, "Support: support@mycruise.com")

    pdf.save()
    return output.getvalue()


async def store_ticket(booking, guests, cabins, cruise, ship, sailing, embark_port=None, disembark_port=None):
    pdf = await ticket_pdf(booking, guests, cabins, cruise, ship, sailing, embark_port, disembark_port)
    stored = put_bytes(
        f"tickets/{booking.booking_reference}.pdf",
        pdf,
        content_type="application/pdf",
    )
    return pdf, stored


async def generate_ticket_after_commit(booking_id):
    """Generate the confirmed ticket and email the PDF attachment."""
    from sqlalchemy import select
    from app.models import Booking, BookingGuest, BookingCabin, Sailing, Cruise, Ship, Port, User

    async with SessionLocal() as session:
        booking = await session.get(Booking, booking_id)
        if not booking:
            return

        guests = (await session.scalars(select(BookingGuest).where(BookingGuest.booking_id == booking.id))).all()
        cabins = (await session.scalars(select(BookingCabin).where(BookingCabin.booking_id == booking.id))).all()
        sailing = await session.get(Sailing, booking.sailing_id)
        if not sailing:
            return
        cruise = await session.get(Cruise, sailing.cruise_id)
        ship = await session.get(Ship, cruise.ship_id) if cruise else None
        embark = await session.get(Port, cruise.embark_port_id) if cruise else None
        disembark = await session.get(Port, cruise.disembark_port_id) if cruise else None
        user = await session.get(User, booking.user_id)
        recipient_email = booking.customer_email or (user.email if user else None)

        try:
            pdf, _stored = await store_ticket(booking, guests, cabins, cruise, ship, sailing, embark, disembark)

            if not recipient_email:
                log.warning("Confirmed booking %s has no recipient email", booking.booking_reference)
                return

            cruise_name = _safe(getattr(cruise, "name", None), "Your cruise")
            body = f"""
                <p>Your <strong>my_cruise</strong> booking is confirmed.</p>
                <p>Your professional e-ticket is attached as a PDF. Please keep it with your passport / travel documents.</p>
                <table role="presentation" width="100%" style="border-collapse:collapse;margin:18px 0">
                  <tr><td style="padding:8px 0;color:#667085;width:150px">Cruise</td><td style="padding:8px 0;font-weight:700">{cruise_name}</td></tr>
                  <tr style="border-top:1px solid #eef1f4"><td style="padding:8px 0;color:#667085">Booking reference</td><td style="padding:8px 0;font-weight:700">{booking.booking_reference}</td></tr>
                  <tr style="border-top:1px solid #eef1f4"><td style="padding:8px 0;color:#667085">Route</td><td style="padding:8px 0;font-weight:700">{_safe(getattr(embark, 'name', None))} to {_safe(getattr(disembark, 'name', None))}</td></tr>
                  <tr style="border-top:1px solid #eef1f4"><td style="padding:8px 0;color:#667085">Total paid</td><td style="padding:8px 0;font-weight:700">{_money(booking.total_cents)} {booking.currency}</td></tr>
                </table>
                <p style="color:#667085;font-size:13px">Attachment: my_cruise-{booking.booking_reference}.pdf</p>
                """
            sent = await send_email(
                recipient_email,
                f"Booking confirmed - my_cruise E-Ticket {booking.booking_reference}",
                wrap_email(
                    "Your booking is confirmed",
                    body,
                    preheader=f"Your my_cruise e-ticket is attached for {booking.booking_reference}",
                ),
                attachments=[(f"my_cruise-{booking.booking_reference}.pdf", pdf, "application/pdf")],
            )
            if sent:
                log.info("E-ticket PDF emailed to %s for booking %s", recipient_email, booking.booking_reference)
            else:
                log.warning("E-ticket PDF was generated but email delivery was not completed for %s", booking.booking_reference)
        except Exception:
            # Payment and booking confirmation must never be rolled back because
            # ticket/email delivery has a separate failure path.
            log.exception("E-ticket generation/email failed for %s", booking.booking_reference)
