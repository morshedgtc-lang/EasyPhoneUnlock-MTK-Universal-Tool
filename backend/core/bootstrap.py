"""Create tables and seed initial config + the single bootstrap admin."""
import logging

from sqlalchemy import select

from backend.core.config import settings
from backend.core.database import Base, SessionLocal, engine
from backend.core.security import hash_password
from backend.models.models import SystemConfig, User

logger = logging.getLogger("bootstrap")


def init_db() -> None:
    # In prod we refuse to come up with insecure configuration.
    if settings.is_prod:
        settings.validate_production()

    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        # Seed default system config.
        defaults = {
            "maintenance_mode": "0",
            "latest_version": settings.APP_VERSION,
            "announcement": "Welcome to EasyPhoneUnlock Universal MTK Tool!",
        }
        for key, value in defaults.items():
            if not db.get(SystemConfig, key):
                db.add(SystemConfig(key=key, value=value))

        # Bootstrap admin. NO hardcoded default password: created only when
        # ADMIN_BOOTSTRAP_PASSWORD is provided, and never if it's a weak value.
        existing = db.scalar(select(User).where(User.username == settings.ADMIN_USERNAME))
        if not existing:
            pw = settings.ADMIN_BOOTSTRAP_PASSWORD
            if pw and pw not in ("admin", "admin123"):
                db.add(User(
                    username=settings.ADMIN_USERNAME,
                    password_hash=hash_password(pw),
                    email=f"{settings.ADMIN_USERNAME}@easyphoneunlock.local",
                    credits=999999, is_active=True, is_admin=True,
                ))
                logger.info("Bootstrap admin '%s' created.", settings.ADMIN_USERNAME)
            else:
                logger.warning(
                    "No admin account exists and ADMIN_BOOTSTRAP_PASSWORD is unset/weak. "
                    "Set it in the environment and restart to create the admin."
                )
        db.commit()
