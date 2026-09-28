import re
from contextlib import asynccontextmanager
from fastapi import FastAPI,Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.core.config import settings
from app.core.database import engine
from app.core.exceptions import AppError,app_error_handler,validation_error_handler,http_exception_handler,unhandled_error_handler
from app.core.logging import RequestIdMiddleware,configure_logging
from app.api.auth import router as auth_router
from app.api.cruises import router as cruise_router
from app.api.bookings import router as booking_router
from app.api.payments import router as payment_router
from app.api.notifications import router as notification_router
from app.api.saved import router as saved_router
from app.api.webhooks import router as webhook_router
from app.api.partners.applications import router as partner_applications_router
from app.api.partners.dashboard import router as partner_dashboard_router
from app.api.partners.bookings import router as partner_bookings_router
from app.api.partners.cruises import router as partner_cruises_router
from app.api.partners.commission import router as partner_commission_router
from app.api.partners.websites import router as partner_websites_router
from app.api.partners.exposure import router as partner_exposure_router
from app.api.partners.api_keys import router as partner_api_keys_router
from app.api.partner_api.cruises import router as partner_api_cruises_router
from app.api.partner_api.bookings import router as partner_api_bookings_router
from app.api.admin.ships import router as admin_ships_router
from app.api.admin.ports import router as admin_ports_router
from app.api.admin.cruises import router as admin_cruises_router
from app.api.admin.cabin_types import router as admin_cabin_types_router
from app.api.admin.sailings import router as admin_sailings_router
from app.api.admin.inventory import router as admin_inventory_router
from app.api.admin.amenities import router as admin_amenities_router
from app.api.admin.dashboard import router as admin_dashboard_router
from app.api.admin.bookings import router as admin_bookings_router
from app.api.admin.cancellations import router as admin_cancellations_router
from app.api.admin.users import router as admin_users_router
from app.api.admin.audit_logs import router as admin_audit_logs_router
from app.api.admin.refund_policies import router as admin_refund_policies_router
from app.tasks.expire_holds import start_scheduler
from app.core.redis import close_redis, get_redis
configure_logging()
@asynccontextmanager
async def lifespan(app):
    scheduler = start_scheduler()
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        await close_redis()
        await engine.dispose()
def _resource_name(path: str) -> str:
    """Turn an API path segment into a readable resource name for Swagger."""
    parts = [p for p in path.split('/') if p and not p.startswith('{')]
    if not parts:
        return 'Resource'
    # Ignore structural segments that are not the actual resource name.
    ignored = {'api', 'auth', 'admin', 'partners', 'partner-api', 'devices'}
    candidates = [p for p in parts if p not in ignored]
    if not candidates:
        return 'Resource'
    value = candidates[-1].replace('-', ' ')
    special = {
        'cruises': 'Cruises', 'ports': 'Ports', 'amenities': 'Amenities',
        'bookings': 'Bookings', 'payments': 'Payments', 'notifications': 'Notifications',
        'saved cruises': 'Saved Cruises', 'refund policies': 'Refund Policies',
        'cancellation requests': 'Cancellation Requests', 'cabin types': 'Cabin Types',
        'sailings': 'Sailings', 'inventory': 'Inventory', 'ships': 'Ships',
        'users': 'Users', 'audit logs': 'Audit Logs', 'websites': 'Partner Websites',
        'applications': 'Partner Applications', 'api keys': 'Partner API Keys',
        'dashboard': 'Dashboard', 'exposures': 'Cruise Exposures', 'commission': 'Commission',
        'itinerary': 'Itinerary', 'images': 'Cruise Images', 'decks': 'Decks', 'cabins': 'Cabins',
        'amenities': 'Amenities', 'token': 'Device Token', 'status': 'Status',
    }
    return special.get(value, value.title())


def _singular_resource(resource: str) -> str:
    """Return a simple singular label for create/update/delete Swagger names."""
    irregular = {'Amenities': 'Amenity', 'Cabin Types': 'Cabin Type', 'Cancellation Requests': 'Cancellation Request', 'Refund Policies': 'Refund Policy', 'Audit Logs': 'Audit Log', 'Partner Websites': 'Partner Website', 'Partner Applications': 'Partner Application', 'Partner API Keys': 'Partner API Key', 'Cruise Images': 'Cruise Image', 'Cruise Exposures': 'Cruise Exposure', 'Saved Cruises': 'Saved Cruise'}
    if resource in irregular:
        return irregular[resource]
    if resource.endswith('ies'):
        return resource[:-3] + 'y'
    if resource.endswith('s') and not resource.endswith('ss'):
        return resource[:-1]
    return resource


def _endpoint_summary(method: str, path: str) -> str:
    """Create short, beginner-friendly Swagger names for every endpoint."""
    key = (method.upper(), path)
    exact = {
        ('POST', '/api/auth/register'): 'Register Traveler',
        ('POST', '/api/auth/login'): 'Login',
        ('POST', '/api/auth/refresh'): 'Refresh Access Token',
        ('POST', '/api/auth/logout'): 'Logout',
        ('GET', '/api/auth/me'): 'Get My Profile',
        ('POST', '/api/auth/verify-email'): 'Verify Email Address',
        ('POST', '/api/auth/forgot-password'): 'Request Password Reset OTP',
        ('POST', '/api/auth/verify-otp'): 'Verify Password Reset OTP',
        ('POST', '/api/auth/resend-otp'): 'Resend Password Reset OTP',
        ('POST', '/api/auth/reset-password'): 'Reset Password',
        ('PATCH', '/api/auth/me'): 'Update My Profile',
        ('POST', '/api/auth/change-password'): 'Change Password',
        ('GET', '/api/cruises'): 'List Available Cruises',
        ('GET', '/api/cruises/featured'): 'List Featured Cruises',
        ('GET', '/api/cruises/{slug}'): 'Get Cruise Details',
        ('GET', '/api/cruises/{slug}/sailings'): 'List Cruise Sailings',
        ('GET', '/api/sailings/{sailing_id}/availability'): 'Check Sailing Cabin Availability',
        ('GET', '/api/ports'): 'List Ports',
        ('GET', '/api/amenities'): 'List Amenities',
        ('POST', '/api/bookings/hold'): 'Hold Cruise Cabins',
        ('GET', '/api/bookings'): 'List My Bookings',
        ('GET', '/api/bookings/{reference}'): 'Get My Booking Details',
        ('POST', '/api/bookings/{reference}/cancel-request'): 'Request Booking Cancellation',
        ('GET', '/api/bookings/{reference}/refund-preview'): 'Preview Booking Refund',
        ('GET', '/api/bookings/{reference}/ticket'): 'Get Booking E-Ticket',
        ('POST', '/api/payments/intent'): 'Create Payment Intent',
        ('GET', '/api/payments/{booking_reference}/status'): 'Get Payment Status',
        ('GET', '/api/notifications'): 'List My Notifications',
        ('PATCH', '/api/notifications/{id}/read'): 'Mark Notification as Read',
        ('PATCH', '/api/notifications/read-all'): 'Mark All Notifications as Read',
        ('GET', '/api/notifications/unread-count'): 'Get Unread Notification Count',
        ('POST', '/api/devices/token'): 'Register Device Token',
        ('DELETE', '/api/devices/token'): 'Remove Device Token',
        ('POST', '/api/webhooks/stripe'): 'Receive Stripe Webhook',
        ('GET', '/api/saved-cruises'): 'List Saved Cruises',
        ('POST', '/api/saved-cruises'): 'Save a Cruise',
        ('DELETE', '/api/saved-cruises/{id}'): 'Remove Saved Cruise',
        ('GET', '/health'): 'Health Check',
        ('GET', '/health/ready'): 'Readiness Check',
    }
    if key in exact:
        return exact[key]

    # Action-oriented endpoints.
    action_map = [
        ('/cancel-request', 'Request Cancellation'),
        ('/payment-intent', 'Create Payment Intent'),
        ('/refund-preview', 'Preview Refund'),
        ('/read-all', 'Mark All as Read'),
        ('/read', 'Mark as Read'),
        ('/unread-count', 'Get Unread Count'),
        ('/verify-email', 'Verify Email Address'),
        ('/verify-otp', 'Verify OTP'),
        ('/resend-otp', 'Resend OTP'),
        ('/reset-password', 'Reset Password'),
        ('/change-password', 'Change Password'),
        ('/review', 'Review Request'),
        ('/publish', 'Publish Cruise'),
        ('/archive', 'Archive Cruise'),
        ('/approve', 'Approve Request'),
        ('/reject', 'Reject Request'),
        ('/revoke', 'Revoke API Key'),
        ('/cancel', 'Cancel Sailing'),
        ('/unblock', 'Unblock Cabin'),
        ('/block', 'Block Cabin'),
        ('/presign', 'Create Image Upload URL'),
    ]
    for suffix, label in action_map:
        if path.endswith(suffix):
            base = path[: -len(suffix)].rstrip('/')
            return f'{label} ({_resource_name(base)})'

    method = method.upper()
    resource = _resource_name(path)
    if method == 'GET':
        if any(part.startswith('{') for part in path.rstrip('/').split('/')):
            return f'Get {resource} Details'
        return f'List {resource}'
    if method == 'POST':
        return f'Create {_singular_resource(resource)}'
    if method in {'PATCH', 'PUT'}:
        return f'Update {_singular_resource(resource)}'
    if method == 'DELETE':
        return f'Delete {_singular_resource(resource)}'
    return f'{method.title()} {resource}'


def _endpoint_tag(path: str) -> str:
    if path.startswith('/api/auth'):
        return 'Authentication'
    if path.startswith('/api/cruises') or path.startswith('/api/ports') or path.startswith('/api/amenities') or path.startswith('/api/sailings'):
        return 'Cruises'
    if path.startswith('/api/bookings'):
        return 'Bookings'
    if path.startswith('/api/payments'):
        return 'Payments'
    if path.startswith('/api/notifications') or path.startswith('/api/devices'):
        return 'Notifications'
    if path.startswith('/api/saved-cruises'):
        return 'Saved Cruises'
    if path.startswith('/api/webhooks/stripe'):
        return 'Stripe Webhooks'
    if path.startswith('/api/partner-api'):
        return 'Partner API'
    if path.startswith('/api/partners'):
        return 'Partner Management'
    if path.startswith('/api/admin/dashboard'):
        return 'Admin - Dashboard'
    admin_resources = [
        ('ships', 'Admin - Ships'), ('ports', 'Admin - Ports'), ('cruises', 'Admin - Cruises'),
        ('cabin-types', 'Admin - Cabin Types'), ('sailings', 'Admin - Sailings'),
        ('inventory', 'Admin - Inventory'), ('amenities', 'Admin - Amenities'),
        ('bookings', 'Admin - Bookings'), ('cancellation-requests', 'Admin - Cancellations'),
        ('refund-policies', 'Admin - Refund Policies'), ('users', 'Admin - Users'),
        ('audit-logs', 'Admin - Audit Logs'),
    ]
    if path.startswith('/api/admin/'):
        for resource, tag in admin_resources:
            if f'/admin/{resource}' in path:
                return tag
        return 'Admin'
    if path.startswith('/health'):
        return 'System'
    return 'System'


def generate_operation_id(route):
    """Generate unique OpenAPI operation IDs from the HTTP method and route path."""
    method = sorted(route.methods or {'GET'})[0].lower()
    path = route.path.removeprefix('/api/').removeprefix('/api')
    slug = re.sub(r'[^a-zA-Z0-9]+', '_', path).strip('_').lower()
    return f'{method}_{slug or "root"}'

app=FastAPI(title='my_cruise API',version='1.0.0',description='my_cruise Phase 1 + Phase 2 traveler, admin and partner booking API',lifespan=lifespan,generate_unique_id_function=generate_operation_id)
app.add_middleware(RequestIdMiddleware)

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Content-Security-Policy'] = ("default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://js.stripe.com; frame-src https://js.stripe.com https://hooks.stripe.com; connect-src 'self' https:; font-src 'self' data: https://fonts.gstatic.com;")
        if settings.APP_ENV != 'development': response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response
app.add_middleware(SecurityHeadersMiddleware)
class PartnerApiUsageMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        started = __import__('time').monotonic()
        response = await call_next(request)
        usage_id = getattr(request.state, 'partner_api_usage_id', None)
        if usage_id:
            try:
                from sqlalchemy import update
                from app.models import PartnerApiUsage
                from app.core.database import SessionLocal
                async with SessionLocal() as session:
                    await session.execute(update(PartnerApiUsage).where(PartnerApiUsage.id == usage_id).values(status_code=response.status_code, duration_ms=int((__import__('time').monotonic()-started)*1000)))
                    await session.commit()
            except Exception:
                import logging; logging.getLogger(__name__).exception('Could not update partner API usage log')
        return response

app.add_middleware(PartnerApiUsageMiddleware)

# CORS is intentionally registered last so it is the outermost middleware.
# This guarantees that even 401/403/500 responses contain CORS headers and
# the browser shows the real API error instead of a misleading CORS failure.
allowed_origins = [
    settings.FRONTEND_URL,
    "http://localhost:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(dict.fromkeys(allowed_origins)),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.add_exception_handler(AppError,app_error_handler)
app.add_exception_handler(RequestValidationError,validation_error_handler)
app.add_exception_handler(StarletteHTTPException,http_exception_handler)
app.add_exception_handler(Exception,unhandled_error_handler)
@app.get('/health')
async def health(): return {'status':'ok'}
@app.get('/health/ready')
async def ready():
    try:
        from sqlalchemy import text
        async with engine.connect() as c: await c.execute(text('SELECT 1'))
        redis_ok = True
        if settings.REDIS_URL:
            r = await get_redis()
            redis_ok = r is not None
        if not redis_ok: return JSONResponse(status_code=503, content={'status':'not_ready','database':True,'redis':False})
        return {'status':'ready','database':True,'redis':redis_ok}
    except Exception as e: return JSONResponse(status_code=503, content={'status':'not_ready','database':False,'error':str(e)})
for r in [
    auth_router, cruise_router, booking_router, payment_router, notification_router, saved_router, webhook_router,
    partner_applications_router, partner_dashboard_router, partner_bookings_router, partner_cruises_router,
    partner_commission_router, partner_websites_router, partner_exposure_router, partner_api_keys_router,
    partner_api_cruises_router, partner_api_bookings_router,
    admin_ships_router, admin_ports_router, admin_cruises_router, admin_cabin_types_router, admin_sailings_router,
    admin_inventory_router, admin_amenities_router, admin_dashboard_router, admin_bookings_router, admin_cancellations_router,
    admin_users_router, admin_audit_logs_router, admin_refund_policies_router,
]: app.include_router(r,prefix=settings.API_PREFIX)

# Apply consistent Swagger grouping and human-readable endpoint names after all routers are registered.
for route in app.routes:
    if hasattr(route, 'methods') and hasattr(route, 'path'):
        method = sorted(route.methods or {'GET'})[0].upper()
        route.summary = _endpoint_summary(method, route.path)
        route.tags = [_endpoint_tag(route.path)]

