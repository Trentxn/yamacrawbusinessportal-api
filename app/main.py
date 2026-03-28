import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import settings
from app.core.rate_limit import limiter
from app.api.controllers import auth, users, businesses, categories, search
from app.api.controllers import service_requests, admin, system_admin, uploads, notifications, reviews, bug_reports, portal_feedback

logger = logging.getLogger(__name__)

AUDIT_LOG_RETENTION_DAYS = 90


def purge_old_audit_logs() -> int:
    """Delete audit logs older than the retention period. Returns count of deleted rows."""
    from app.db.session import SessionLocal
    from app.models.audit import AuditLog

    cutoff = datetime.now(timezone.utc) - timedelta(days=AUDIT_LOG_RETENTION_DAYS)
    db = SessionLocal()
    try:
        count = db.query(AuditLog).filter(AuditLog.timestamp < cutoff).delete()
        db.commit()
        return count
    finally:
        db.close()


async def _audit_log_cleanup_loop():
    """Run audit log purge once on startup, then every 24 hours."""
    while True:
        try:
            deleted = await asyncio.to_thread(purge_old_audit_logs)
            if deleted:
                logger.info("Purged %d audit log entries older than %d days", deleted, AUDIT_LOG_RETENTION_DAYS)
        except Exception:
            logger.exception("Failed to purge old audit logs")
        await asyncio.sleep(86400)  # 24 hours


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_audit_log_cleanup_loop())
    yield
    task.cancel()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Trusted hosts
if not settings.DEBUG:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["yamacrawbusinessportal.com", "www.yamacrawbusinessportal.com", "localhost"],
    )

# Routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(businesses.router, prefix="/api/businesses", tags=["businesses"])
app.include_router(categories.router, prefix="/api/categories", tags=["categories"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(service_requests.router, prefix="/api/service-requests", tags=["service-requests"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(system_admin.router, prefix="/api/system-admin", tags=["system-admin"])
app.include_router(uploads.router, prefix="/api/uploads", tags=["uploads"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])
app.include_router(reviews.router, prefix="/api/reviews", tags=["reviews"])
app.include_router(bug_reports.router, prefix="/api/bug-reports", tags=["bug-reports"])
app.include_router(portal_feedback.router, prefix="/api/portal-feedback", tags=["Portal Feedback"])


@app.get("/health")
def health_check():
    return {"status": "ok", "version": settings.APP_VERSION}
