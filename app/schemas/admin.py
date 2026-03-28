from __future__ import annotations

from app.schemas.common import CamelModel


class CategoryCount(CamelModel):
    name: str
    count: int


class AdminStatsResponse(CamelModel):
    total_businesses: int
    pending_approvals: int
    total_users: int
    total_inquiries: int
    inquiries_this_month: int
    top_categories: list[CategoryCount]


class BusinessApproval(CamelModel):
    pass


class BusinessRejection(CamelModel):
    reason: str


class BusinessSuspension(CamelModel):
    reason: str
