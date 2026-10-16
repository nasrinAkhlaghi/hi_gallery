"""Set non-secret local defaults before application modules are imported in tests."""

import os

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///./unused-test-database.db")
os.environ.setdefault("JWT_SIGNING_KEY", "test-only-jwt-signing-key-not-for-any-deployment")
os.environ.setdefault("CSRF_SIGNING_KEY", "test-only-csrf-signing-key-not-for-any-deployment")
os.environ.setdefault("AUTH_ISSUER", "https://test.hi-gallery.invalid")
os.environ.setdefault("AUTH_AUDIENCE", "hi-gallery-test")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("CORS_ALLOWED_ORIGINS", "http://testserver,http://localhost:5173")
