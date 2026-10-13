"""
Pytest setup. Sets a test environment BEFORE any backend module is imported, so
the backend uses an isolated SQLite DB and a throwaway vault key. Must run at
import time (pytest imports conftest first).
"""
import os
import tempfile

_TEST_DIR = tempfile.mkdtemp(prefix="epu_tests_")
os.environ.setdefault("ENV", "dev")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DIR.replace(os.sep, '/')}/test.db"
os.environ["PAYLOAD_DIR"] = os.path.join(_TEST_DIR, "vault")
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_BOOTSTRAP_PASSWORD"] = "Str0ng!Admin"
os.environ["LOGIN_MAX_ATTEMPTS"] = "50"  # don't trip lockout during tests
# A fixed test Fernet key so the vault works in tests.
os.environ["PAYLOAD_ENC_KEY"] = "u7m3Xq2bJc8wVz1aPeR4tY6sN0kD5gH9lLoI3uQfBvE="
