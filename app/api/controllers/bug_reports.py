import math
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_verified_user, require_role
from app.db.session import get_db
from app.models.bug_report import BugReport
from app.models.user import User
from app.schemas.bug_report import BugReportCreate, BugReportResolve, BugReportResponse
from app.schemas.common import MessageResponse, PaginatedResponse

router = APIRouter()


def _to_response(report: BugReport) -> BugReportResponse:
    resolver_name = None
    if report.resolver:
        resolver_name = f"{report.resolver.first_name} {report.resolver.last_name}"

    return BugReportResponse(
        id=report.id,
        user_id=report.user_id,
        user_email=report.user_email,
        user_name=report.user_name,
        subject=report.subject,
        description=report.description,
        page_url=report.page_url,
        user_agent=report.user_agent,
        status=report.status,
        resolved_by=report.resolved_by,
        resolver_name=resolver_name,
        resolution_note=report.resolution_note,
        resolved_at=report.resolved_at,
        created_at=report.created_at,
    )


@router.post(
    "/",
    response_model=BugReportResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_bug_report(
    body: BugReportCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
):
    """Submit a bug report (any authenticated user)."""
    report = BugReport(
        user_id=current_user.id,
        user_email=current_user.email,
        user_name=f"{current_user.first_name} {current_user.last_name}",
        subject=body.subject,
        description=body.description,
        page_url=body.page_url,
        user_agent=request.headers.get("user-agent"),
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return _to_response(report)


# ---------------------------------------------------------------------------
# System admin endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/",
    response_model=PaginatedResponse[BugReportResponse],
)
def list_bug_reports(
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("system_admin", "admin")),
):
    """List all bug reports (system admin only)."""
    base_query = db.query(BugReport)

    if status_filter:
        base_query = base_query.filter(BugReport.status == status_filter)

    total = base_query.count()
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    reports = (
        base_query
        .order_by(BugReport.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return PaginatedResponse(
        items=[_to_response(r) for r in reports],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.put(
    "/{report_id}",
    response_model=BugReportResponse,
)
def update_bug_report(
    report_id: uuid.UUID,
    body: BugReportResolve,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("system_admin", "admin")),
):
    """Update bug report status (system admin only)."""
    report = db.query(BugReport).filter(BugReport.id == report_id).first()
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bug report not found",
        )

    report.status = body.status
    if body.resolution_note:
        report.resolution_note = body.resolution_note

    if body.status in ("resolved", "dismissed"):
        report.resolved_by = current_user.id
        report.resolved_at = datetime.now(timezone.utc)
    elif body.status == "in_progress":
        report.resolved_by = None
        report.resolved_at = None

    db.commit()
    db.refresh(report)
    return _to_response(report)
