"""Safe defaults for unit tests that do not require live infrastructure."""
import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret-key-change-me")
os.environ.setdefault("ADMIN_INITIAL_PASSWORD", "TestAdmin@12345")
