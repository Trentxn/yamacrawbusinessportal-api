from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.business import Business
from app.models.category import Category
from app.models.enums import BusinessStatus
from app.schemas.category import CategoryResponse

router = APIRouter()


@router.get(
    "/",
    response_model=list[CategoryResponse],
)
def list_categories(db: Session = Depends(get_db)):
    """List all active categories with the count of approved businesses in each."""
    results = (
        db.query(
            Category,
            func.count(Business.id).label("business_count"),
        )
        .outerjoin(
            Business,
            (Business.category_id == Category.id)
            & (Business.status == BusinessStatus.approved),
        )
        .filter(Category.is_active.is_(True))
        .group_by(Category.id)
        .order_by(Category.sort_order, Category.name)
        .all()
    )

    return [
        CategoryResponse(
            id=cat.id,
            name=cat.name,
            slug=cat.slug,
            description=cat.description,
            icon=cat.icon,
            sort_order=cat.sort_order,
            business_count=count,
        )
        for cat, count in results
    ]


@router.get(
    "/{slug}",
    response_model=CategoryResponse,
)
def get_category(slug: str, db: Session = Depends(get_db)):
    """Get a single active category by slug with the count of approved businesses."""
    result = (
        db.query(
            Category,
            func.count(Business.id).label("business_count"),
        )
        .outerjoin(
            Business,
            (Business.category_id == Category.id)
            & (Business.status == BusinessStatus.approved),
        )
        .filter(Category.slug == slug, Category.is_active.is_(True))
        .group_by(Category.id)
        .first()
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )

    cat, count = result
    return CategoryResponse(
        id=cat.id,
        name=cat.name,
        slug=cat.slug,
        description=cat.description,
        icon=cat.icon,
        sort_order=cat.sort_order,
        business_count=count,
    )
