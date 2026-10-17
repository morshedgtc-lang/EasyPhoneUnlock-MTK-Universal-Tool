"""Create tables and seed initial config + the single bootstrap admin.

Safe to run from several gunicorn workers at once: every seed insert is its own
transaction guarded against the UniqueViolation another worker may win the race
with, so concurrent startup never crashes.
"""
import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.core.config import settings
from backend.core.database import Base, SessionLocal, engine
from backend.core.security import hash_password
from backend.models.models import SystemConfig, User

logger = logging.getLogger("bootstrap")


def _seed_once(db, obj_factory, exists_query) -> None:
    """Insert obj if it doesn't exist; tolerate a concurrent worker inserting it."""
    if db.scalar(exists_query) is not None:
        return
    db.add(obj_factory())
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # another worker seeded it first — fine.


def init_db() -> None:
    # In prod we refuse to come up with insecure configuration.
    if settings.is_prod:
        settings.validate_production()

    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        defaults = {
            "maintenance_mode": "0",
            "latest_version": settings.APP_VERSION,
            "announcement": "Welcome to EasyPhoneUnlock Universal MTK Tool!",
        }
        for key, value in defaults.items():
            _seed_once(
                db,
                lambda k=key, v=value: SystemConfig(key=k, value=v),
                select(SystemConfig).where(SystemConfig.key == key),
            )

        # Bootstrap admin. NO hardcoded default password: created only when
        # ADMIN_BOOTSTRAP_PASSWORD is provided, and never if it's a weak value.
        pw = settings.ADMIN_BOOTSTRAP_PASSWORD
        if pw and pw not in ("admin", "admin123"):
            _seed_once(
                db,
                lambda: User(
                    username=settings.ADMIN_USERNAME,
                    password_hash=hash_password(pw),
                    email=f"{settings.ADMIN_USERNAME}@easyphoneunlock.local",
                    credits=999999, is_active=True, is_admin=True,
                ),
                select(User).where(User.username == settings.ADMIN_USERNAME),
            )
        elif db.scalar(select(User).where(User.username == settings.ADMIN_USERNAME)) is None:
            logger.warning(
                "No admin account exists and ADMIN_BOOTSTRAP_PASSWORD is unset/weak. "
                "Set it in the environment and restart to create the admin."
            )
