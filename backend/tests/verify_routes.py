"""Static verification of Phase 1 endpoint paths.

This check does not connect to PostgreSQL. It parses router decorators so it can
be used immediately after checkout, before installing infrastructure services.
"""
from pathlib import Path
import ast
import re

ROOT = Path(__file__).resolve().parents[1] / "app" / "api"

def routes():
    found = set()
    for path in ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        prefix = ""
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                if isinstance(node.value.func, ast.Name) and node.value.func.id == "APIRouter":
                    for kw in node.value.keywords:
                        if kw.arg == "prefix" and isinstance(kw.value, ast.Constant):
                            prefix = kw.value.value
        for node in ast.walk(tree):
            if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                continue
            for dec in node.decorator_list:
                if not (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)):
                    continue
                if not (isinstance(dec.func.value, ast.Name) and dec.func.value.id == "router"):
                    continue
                if not dec.args or not isinstance(dec.args[0], ast.Constant):
                    continue
                method = dec.func.attr.upper()
                path_value = "/api" + prefix + dec.args[0].value
                found.add((method, path_value))
    return found

EXPECTED = {
    ("POST", "/api/auth/register"), ("POST", "/api/auth/login"),
    ("POST", "/api/auth/refresh"), ("POST", "/api/auth/logout"),
    ("GET", "/api/auth/me"), ("POST", "/api/auth/forgot-password"),
    ("POST", "/api/auth/verify-otp"), ("POST", "/api/auth/resend-otp"),
    ("POST", "/api/auth/reset-password"), ("PATCH", "/api/auth/me"),
    ("POST", "/api/auth/change-password"),
    ("GET", "/api/cruises"), ("GET", "/api/cruises/featured"),
    ("GET", "/api/cruises/{slug}"), ("GET", "/api/cruises/{slug}/sailings"),
    ("GET", "/api/sailings/{sailing_id}/availability"),
    ("GET", "/api/ports"), ("GET", "/api/amenities"),
    ("GET", "/api/saved-cruises"), ("POST", "/api/saved-cruises"),
    ("DELETE", "/api/saved-cruises/{id}"),
    ("POST", "/api/bookings/hold"), ("GET", "/api/bookings"),
    ("GET", "/api/bookings/{reference}"),
    ("GET", "/api/bookings/{reference}/ticket"),
    ("POST", "/api/bookings/{reference}/cancel-request"),
    ("GET", "/api/bookings/{reference}/refund-preview"),
    ("POST", "/api/payments/intent"),
    ("GET", "/api/payments/{booking_reference}/status"),
    ("GET", "/api/notifications"), ("PATCH", "/api/notifications/{id}/read"),
    ("PATCH", "/api/notifications/read-all"),
    ("GET", "/api/notifications/unread-count"),
    ("POST", "/api/devices/token"), ("DELETE", "/api/devices/token"),
    ("POST", "/api/webhooks/stripe"),
    ("GET", "/api/admin/dashboard/stats"),
    ("GET", "/api/admin/ships"), ("POST", "/api/admin/ships"),
    ("PATCH", "/api/admin/ships/{id}"), ("DELETE", "/api/admin/ships/{id}"),
    ("GET", "/api/admin/ports"), ("POST", "/api/admin/ports"),
    ("PATCH", "/api/admin/ports/{id}"), ("DELETE", "/api/admin/ports/{id}"),
    ("GET", "/api/admin/cruises"), ("POST", "/api/admin/cruises"),
    ("PATCH", "/api/admin/cruises/{id}"), ("DELETE", "/api/admin/cruises/{id}"),
    ("POST", "/api/admin/cruises/{id}/publish"),
    ("POST", "/api/admin/cruises/{id}/archive"),
    ("POST", "/api/admin/cruises/{id}/images"),
    ("PUT", "/api/admin/cruises/{id}/itinerary"),
    ("GET", "/api/admin/cruises/{id}/cabin-types"),
    ("POST", "/api/admin/cruises/{id}/cabin-types"),
    ("PATCH", "/api/admin/cruises/{id}/cabin-types/{ct_id}"),
    ("PUT", "/api/admin/cruises/{id}/cabin-types/{ct_id}/amenities"),
    ("POST", "/api/admin/ships/{ship_id}/decks"),
    ("POST", "/api/admin/ships/{ship_id}/cabins"),
    ("GET", "/api/admin/sailings"), ("POST", "/api/admin/sailings"),
    ("PATCH", "/api/admin/sailings/{id}"),
    ("GET", "/api/admin/sailings/{id}/inventory"),
    ("PATCH", "/api/admin/sailings/{sailing_id}/cabins/{cabin_id}/block"),
    ("POST", "/api/admin/sailings/{id}/cancel"),
    ("GET", "/api/admin/bookings"), ("GET", "/api/admin/bookings/{reference}"),
    ("GET", "/api/admin/cancellation-requests"),
    ("GET", "/api/admin/cancellation-requests/{id}"),
    ("POST", "/api/admin/cancellation-requests/{id}/approve"),
    ("POST", "/api/admin/cancellation-requests/{id}/reject"),
    ("GET", "/api/admin/refund-policies"), ("POST", "/api/admin/refund-policies"),
    ("PUT", "/api/admin/refund-policies/{id}/rules"),
    ("GET", "/api/admin/users"), ("POST", "/api/admin/users"),
    ("PATCH", "/api/admin/users/{id}/status"),
    ("GET", "/api/admin/audit-logs"),
}

if __name__ == "__main__":
    actual = routes()
    missing = sorted(EXPECTED - actual)
    if missing:
        raise SystemExit("Missing Phase 1 routes:\n" + "\n".join(f"{m} {p}" for m, p in missing))
    print(f"PASS: all {len(EXPECTED)} required Phase 1 endpoint method/path combinations are present.")
    print(f"Total router combinations found: {len(actual)}")
