"""Seed script for initial categories and system admin account.

Usage:
    python -m scripts.seed

Run this after the database migration has been applied.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.category import Category
from app.models.enums import UserRole, UserStatus
from app.models.user import User


INITIAL_CATEGORIES = [
    {"name": "Restaurants & Food", "slug": "restaurants-food", "icon": "utensils", "sort_order": 1},
    {"name": "Auto Services", "slug": "auto-services", "icon": "car", "sort_order": 2},
    {"name": "Home Services", "slug": "home-services", "icon": "home", "sort_order": 3},
    {"name": "Beauty & Wellness", "slug": "beauty-wellness", "icon": "sparkles", "sort_order": 4},
    {"name": "Construction & Trades", "slug": "construction-trades", "icon": "hammer", "sort_order": 5},
    {"name": "Cleaning Services", "slug": "cleaning-services", "icon": "spray-can", "sort_order": 6},
    {"name": "Electrical & Plumbing", "slug": "electrical-plumbing", "icon": "zap", "sort_order": 7},
    {"name": "Landscaping & Gardening", "slug": "landscaping-gardening", "icon": "trees", "sort_order": 8},
    {"name": "Technology & IT", "slug": "technology-it", "icon": "monitor", "sort_order": 9},
    {"name": "Professional Services", "slug": "professional-services", "icon": "briefcase", "sort_order": 10},
    {"name": "Education & Tutoring", "slug": "education-tutoring", "icon": "graduation-cap", "sort_order": 11},
    {"name": "Health & Medical", "slug": "health-medical", "icon": "heart-pulse", "sort_order": 12},
    {"name": "Retail & Shopping", "slug": "retail-shopping", "icon": "shopping-bag", "sort_order": 13},
    {"name": "Events & Entertainment", "slug": "events-entertainment", "icon": "music", "sort_order": 14},
    {"name": "Transportation", "slug": "transportation", "icon": "truck", "sort_order": 15},
    {"name": "Pet Services", "slug": "pet-services", "icon": "paw-print", "sort_order": 16},
    {"name": "Photography & Media", "slug": "photography-media", "icon": "camera", "sort_order": 17},
    {"name": "Financial Services", "slug": "financial-services", "icon": "landmark", "sort_order": 18},
    {"name": "Other Services", "slug": "other-services", "icon": "grid-3x3", "sort_order": 99},
]

SYSTEM_ADMIN = {
    "email": "admin@yamacrawbusinessportal.com",
    "password": "Admin@YBP2026!",
    "first_name": "System",
    "last_name": "Admin",
}


def seed_categories(db):
    existing = {c.slug for c in db.query(Category.slug).all()}
    created = 0
    for cat_data in INITIAL_CATEGORIES:
        if cat_data["slug"] not in existing:
            db.add(Category(**cat_data))
            created += 1
    db.commit()
    print(f"Categories: {created} created, {len(existing)} already existed")


def seed_system_admin(db):
    existing = db.query(User).filter(User.email == SYSTEM_ADMIN["email"]).first()
    if existing:
        print(f"System admin already exists: {SYSTEM_ADMIN['email']}")
        return

    admin = User(
        email=SYSTEM_ADMIN["email"],
        hashed_password=hash_password(SYSTEM_ADMIN["password"]),
        first_name=SYSTEM_ADMIN["first_name"],
        last_name=SYSTEM_ADMIN["last_name"],
        role=UserRole.system_admin,
        status=UserStatus.active,
        email_verified=True,
    )
    db.add(admin)
    db.commit()
    print(f"System admin created: {SYSTEM_ADMIN['email']}")
    print(f"  Password: {SYSTEM_ADMIN['password']}")
    print("  ** CHANGE THIS PASSWORD IMMEDIATELY IN PRODUCTION **")


def main():
    print("Seeding database...")
    db = SessionLocal()
    try:
        seed_categories(db)
        seed_system_admin(db)
        print("Done!")
    finally:
        db.close()


if __name__ == "__main__":
    main()
