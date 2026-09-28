"""Transactional email service for OTP, booking and refund messages.

SMTP is optional in local development; when it is not configured we log only
the event metadata and never log OTPs, passwords or payment data.

All outgoing emails are rendered through `wrap_email`, a single branded
HTML template, so every transactional message (OTP, booking confirmation,
cancellation, refund, partner approval, admin notices) looks like a real
product email rather than a bare HTML fragment.
"""
import logging
from pathlib import Path
from app.core.config import settings

log = logging.getLogger(__name__)

BRAND_NAME = "my_cruise"
BRAND_INK = "#0b1d2a"      # navy-900 — matches the app's header/footer color
BRAND_TEAL = "#0b8277"     # brand-600 — matches the app's primary accent
BRAND_TEAL_DARK = "#08665e"  # brand-700
SUPPORT_EMAIL = "support@mycruise.com"


def wrap_email(title: str, body_html: str, preheader: str = "", cta_label: str | None = None, cta_url: str | None = None) -> str:
    """Wrap inner content in a branded, responsive HTML email shell.

    title: shown as the header line under the logo mark.
    body_html: pre-built inner HTML (paragraphs, tables, lists). Caller controls content;
               this only controls the surrounding chrome so every email is on-brand.
    preheader: short hidden preview text shown in inbox lists (Gmail/Outlook), not in the body.
    cta_label/cta_url: optional single call-to-action button.
    """
    cta_html = ""
    if cta_label and cta_url:
        cta_html = f'''
        <tr><td align="center" style="padding:8px 40px 32px">
          <a href="{cta_url}" style="background:{BRAND_TEAL};color:#ffffff;text-decoration:none;font-weight:700;
             font-size:15px;padding:14px 28px;border-radius:10px;display:inline-block">{cta_label}</a>
        </td></tr>'''
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{title}</title>
</head>
<body style="margin:0;padding:0;background:#eef2f5;font-family:'Segoe UI',Helvetica,Arial,sans-serif;">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0">{preheader}</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#eef2f5;padding:32px 16px">
    <tr><td align="center">
      <table role="presentation" width="600" cellpadding="0" cellspacing="0"
             style="background:#ffffff;border-radius:16px;overflow:hidden;max-width:600px;width:100%;
                    box-shadow:0 6px 24px rgba(7,21,33,.08)">
        <tr>
          <td style="background:linear-gradient(135deg,{BRAND_INK} 0%,#102c3d 55%,{BRAND_TEAL_DARK} 100%);
                     padding:28px 40px;">
            <table role="presentation" width="100%"><tr>
              <td>
                <span style="display:inline-block;width:36px;height:36px;border-radius:10px;background:rgba(255,255,255,.14);
                     color:#ffffff;font-weight:800;font-size:18px;text-align:center;line-height:36px;vertical-align:middle">M</span>
                <span style="color:#ffffff;font-weight:800;font-size:18px;letter-spacing:.2px;vertical-align:middle;margin-left:10px">{BRAND_NAME}</span>
              </td>
            </tr></table>
          </td>
        </tr>
        <tr><td style="padding:36px 40px 8px">
          <h1 style="margin:0 0 18px;font-size:22px;color:{BRAND_INK};font-weight:800">{title}</h1>
          <div style="font-size:15px;line-height:1.65;color:#334155">{body_html}</div>
        </td></tr>
        {cta_html}
        <tr><td style="padding:0 40px 36px">
          <hr style="border:none;border-top:1px solid #e5e9ee;margin:8px 0 20px"/>
          <p style="margin:0 0 6px;font-size:12.5px;color:#8a97a6">
            Need help? Contact us at <a href="mailto:{SUPPORT_EMAIL}" style="color:{BRAND_TEAL_DARK};text-decoration:none">{SUPPORT_EMAIL}</a>.
          </p>
          <p style="margin:0;font-size:12px;color:#a7b1bd">
            &copy; {BRAND_NAME.replace('_', ' ').title()}. This is an automated message — please do not reply directly to this email.
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>'''


async def send_email(to: str, subject: str, html: str, attachments=None):
    """Send an HTML email, optionally with real file attachments.

    Uses Python's standard SMTP/MIME implementation so PDF attachments are
    encoded explicitly and reliably on Windows.  `attachments` may contain
    file paths or `(filename, bytes, content_type)` tuples.
    """
    if not settings.SMTP_HOST or not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        log.warning("Email not sent because SMTP is not configured: %s", subject)
        return False

    from email.message import EmailMessage
    from email.utils import formataddr
    from pathlib import Path
    import mimetypes
    import smtplib

    try:
        sender = settings.MAIL_FROM or settings.SMTP_USER
        message = EmailMessage()
        message["From"] = sender
        message["To"] = to
        message["Subject"] = subject
        message.set_content("Please open this email in an HTML-capable mail client.")
        message.add_alternative(html, subtype="html")

        for attachment in attachments or []:
            filename = None
            data = None
            content_type = None

            if isinstance(attachment, tuple) and len(attachment) == 3:
                filename, data, content_type = attachment
                if isinstance(data, str):
                    data = Path(data).read_bytes()
            else:
                path = Path(str(attachment))
                filename = path.name
                data = path.read_bytes()

            if not data:
                raise ValueError(f"Attachment is empty: {filename}")

            if not content_type:
                content_type = mimetypes.guess_type(filename or "attachment")[0] or "application/octet-stream"
            maintype, subtype = content_type.split("/", 1)
            message.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)

        # Gmail SMTP submission uses STARTTLS on port 587.
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as smtp:
            smtp.ehlo()
            if settings.SMTP_PORT != 465:
                smtp.starttls()
                smtp.ehlo()
            smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            smtp.send_message(message)

        log.info("Email sent successfully: subject=%s recipient=%s attachments=%s", subject, to, len(attachments or []))
        return True
    except Exception:
        log.exception("Email delivery failed for subject=%s recipient=%s", subject, to)
        return False


def otp_email(code: str, purpose: str) -> tuple[str, str]:
    title = "Verify your email" if purpose == "email_verify" else "Reset your password"
    subject = f"{BRAND_NAME} — {title}"
    body = f'''
    <p>Use the verification code below to continue. It's valid for the next
    <b>{settings.OTP_EXPIRY_MINUTES} minutes</b>.</p>
    <table role="presentation" width="100%" style="margin:20px 0"><tr><td align="center">
      <div style="display:inline-block;background:#f3f7f6;border:1px solid #dfeae8;border-radius:12px;
                  padding:16px 28px;font-size:32px;font-weight:800;letter-spacing:10px;color:{BRAND_INK}">{code}</div>
    </td></tr></table>
    <p style="color:#8a97a6;font-size:13.5px">If you didn't request this, you can safely ignore this email —
    your account is still secure.</p>'''
    html = wrap_email(title, body, preheader=f"Your {BRAND_NAME} verification code is {code}")
    return subject, html


def booking_confirmation_email(cruise_name: str, reference: str, ticket_attached: bool = True) -> tuple[str, str]:
    subject = f"Booking confirmed — {reference}"
    ticket_text = ("Your e-ticket is attached to this email as a PDF." if ticket_attached
                   else "Your e-ticket is being prepared and will be available shortly from My Bookings.")
    body = f'''
    <p>Great news — your booking is confirmed. Here are the details:</p>
    <table role="presentation" width="100%" style="border-collapse:collapse;margin:16px 0">
      <tr><td style="padding:8px 0;color:#8a97a6;width:140px">Cruise</td><td style="padding:8px 0;font-weight:700">{cruise_name}</td></tr>
      <tr style="border-top:1px solid #eef1f4"><td style="padding:8px 0;color:#8a97a6">Booking reference</td><td style="padding:8px 0;font-weight:700">{reference}</td></tr>
    </table>
    <p>{ticket_text}</p>'''
    html = wrap_email("Booking confirmed", body, preheader=f"Your booking {reference} is confirmed")
    return subject, html


def cancellation_email(reference: str, approved: bool, amount_cents: int = 0, reason: str | None = None) -> tuple[str, str]:
    state = "approved" if approved else "rejected"
    subject = f"Cancellation request {state} — {reference}"
    body = f'<p>Your cancellation request for booking <b>{reference}</b> has been <b>{state}</b>.</p>'
    if approved:
        body += f'''<table role="presentation" width="100%" style="border-collapse:collapse;margin:16px 0">
          <tr><td style="padding:8px 0;color:#8a97a6;width:160px">Refund amount</td>
          <td style="padding:8px 0;font-weight:800;color:{BRAND_TEAL_DARK};font-size:17px">${amount_cents / 100:.2f} USD</td></tr>
        </table><p style="color:#8a97a6;font-size:13.5px">Refunds typically appear on your original payment method within 5–10 business days.</p>'''
    elif reason:
        body += f'<p style="background:#f7f8fa;border-radius:10px;padding:12px 16px;margin-top:12px"><b>Admin note:</b> {reason}</p>'
    html = wrap_email(f"Cancellation {state}", body, preheader=f"Your cancellation request for {reference} was {state}")
    return subject, html


def refund_email(reference: str, amount_cents: int) -> tuple[str, str]:
    subject = f"Refund completed — {reference}"
    body = f'''<p>Your refund for booking <b>{reference}</b> has been processed successfully.</p>
    <table role="presentation" width="100%" style="border-collapse:collapse;margin:16px 0">
      <tr><td style="padding:8px 0;color:#8a97a6;width:160px">Refund amount</td>
      <td style="padding:8px 0;font-weight:800;color:{BRAND_TEAL_DARK};font-size:17px">${amount_cents / 100:.2f} USD</td></tr>
    </table>
    <p style="color:#8a97a6;font-size:13.5px">Refunds typically appear on your original payment method within 5–10 business days.</p>'''
    html = wrap_email("Refund completed", body, preheader=f"Your refund of ${amount_cents/100:.2f} for {reference} is complete")
    return subject, html
