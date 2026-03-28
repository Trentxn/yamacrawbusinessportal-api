"""Seed script for test/demo data. Run AFTER seed.py.

Usage (inside api container):
    python -m scripts.seed_test_data

Creates:
  - 1 admin user
  - 3 business owners with approved/featured businesses
  - 1 business owner with a pending listing
  - 2 public users with inquiries
  - Service requests in various statuses

All test accounts use the same password: Test@2026!
"""

import sys
import os
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.category import Category
from app.models.user import User
from app.models.business import Business, BusinessTag, BusinessViewStats
from app.models.service_request import ServiceRequest
from app.models.enums import (
    UserRole,
    UserStatus,
    BusinessStatus,
    ServiceRequestStatus,
    ListingType,
)

PASSWORD = "Test@2026!"
NOW = datetime.now(timezone.utc)


# ── Users ──────────────────────────────────────────────────────────────────

TEST_USERS = [
    {
        "email": "admin@test.com",
        "first_name": "Angela",
        "last_name": "Rolle",
        "role": UserRole.admin,
        "phone": "242-555-0100",
    },
    {
        "email": "owner1@test.com",
        "first_name": "Marcus",
        "last_name": "Thompson",
        "role": UserRole.business_owner,
        "phone": "242-555-0201",
    },
    {
        "email": "owner2@test.com",
        "first_name": "Shantell",
        "last_name": "Ferguson",
        "role": UserRole.business_owner,
        "phone": "242-555-0202",
    },
    {
        "email": "owner3@test.com",
        "first_name": "Derek",
        "last_name": "Moss",
        "role": UserRole.business_owner,
        "phone": "242-555-0203",
    },
    {
        "email": "owner4@test.com",
        "first_name": "Tamika",
        "last_name": "Saunders",
        "role": UserRole.business_owner,
        "phone": "242-555-0204",
    },
    {
        "email": "user1@test.com",
        "first_name": "James",
        "last_name": "Knowles",
        "role": UserRole.public_user,
        "phone": "242-555-0301",
    },
    {
        "email": "user2@test.com",
        "first_name": "Crystal",
        "last_name": "Bethel",
        "role": UserRole.public_user,
        "phone": "242-555-0302",
    },
    {
        "email": "contractor1@test.com",
        "first_name": "Ricardo",
        "last_name": "Bain",
        "role": UserRole.business_owner,
        "phone": "242-555-0401",
    },
    {
        "email": "contractor2@test.com",
        "first_name": "Patricia",
        "last_name": "Wells",
        "role": UserRole.business_owner,
        "phone": "242-555-0402",
    },
    {
        "email": "contractor3@test.com",
        "first_name": "Anthony",
        "last_name": "Cartwright",
        "role": UserRole.business_owner,
        "phone": "242-555-0403",
    },
]

# ── Businesses (matched to owners by email) ────────────────────────────────

TEST_BUSINESSES = [
    {
        "owner_email": "owner1@test.com",
        "category_slug": "restaurants-food",
        "name": "Island Flavors Kitchen",
        "slug": "island-flavors-kitchen",
        "short_description": "Authentic Bahamian cuisine made fresh daily with locally sourced ingredients.",
        "description": "Island Flavors Kitchen has been serving the Yamacraw community for over 10 years. We specialise in traditional Bahamian dishes including conch salad, cracked lobster, peas and rice, and our famous guava duff. Catering available for events of all sizes.",
        "phone": "242-555-1001",
        "email": "info@islandflavors.com",
        "website": "https://islandflavors.com",
        "address_line1": "42 Yamacraw Road",
        "settlement": "Yamacraw",
        "status": BusinessStatus.approved,
        "is_featured": True,
        "operating_hours": {
            "monday": {"open": "07:00", "close": "21:00"},
            "tuesday": {"open": "07:00", "close": "21:00"},
            "wednesday": {"open": "07:00", "close": "21:00"},
            "thursday": {"open": "07:00", "close": "21:00"},
            "friday": {"open": "07:00", "close": "22:00"},
            "saturday": {"open": "08:00", "close": "22:00"},
            "sunday": {"open": "08:00", "close": "15:00"},
        },
        "social_links": {"facebook": "https://facebook.com/islandflavors", "instagram": "https://instagram.com/islandflavors"},
        "tags": ["Bahamian Food", "Catering", "Takeout", "Dine-In"],
    },
    {
        "owner_email": "owner1@test.com",
        "category_slug": "restaurants-food",
        "name": "Thompson's Snack Shack",
        "slug": "thompsons-snack-shack",
        "short_description": "Quick bites, smoothies, and island snacks right on the corner.",
        "description": "A grab-and-go spot for students, workers, and families. Fresh juices, conch fritters, johnny cake sandwiches, and more. Open early for the morning rush.",
        "phone": "242-555-1002",
        "email": "snacks@thompson.com",
        "address_line1": "18 Prince Charles Drive",
        "settlement": "Yamacraw",
        "status": BusinessStatus.approved,
        "is_featured": False,
        "operating_hours": {
            "monday": {"open": "06:00", "close": "18:00"},
            "tuesday": {"open": "06:00", "close": "18:00"},
            "wednesday": {"open": "06:00", "close": "18:00"},
            "thursday": {"open": "06:00", "close": "18:00"},
            "friday": {"open": "06:00", "close": "20:00"},
            "saturday": {"open": "07:00", "close": "16:00"},
            "sunday": "closed",
        },
        "tags": ["Snacks", "Smoothies", "Quick Bites"],
    },
    {
        "owner_email": "owner2@test.com",
        "category_slug": "beauty-wellness",
        "name": "Shantell's Glow Studio",
        "slug": "shantells-glow-studio",
        "short_description": "Premium hair, nails, and skincare services for the modern woman.",
        "description": "At Shantell's Glow Studio, we believe every woman deserves to feel beautiful. We offer braiding, locs, relaxers, manicures, pedicures, facials, and waxing. Our stylists have over 15 years of combined experience. Walk-ins welcome, appointments preferred.",
        "phone": "242-555-2001",
        "email": "book@shantellsglow.com",
        "website": "https://shantellsglow.com",
        "address_line1": "7 Sea Breeze Lane",
        "settlement": "Yamacraw",
        "status": BusinessStatus.approved,
        "is_featured": True,
        "operating_hours": {
            "monday": "closed",
            "tuesday": {"open": "09:00", "close": "18:00"},
            "wednesday": {"open": "09:00", "close": "18:00"},
            "thursday": {"open": "09:00", "close": "18:00"},
            "friday": {"open": "09:00", "close": "19:00"},
            "saturday": {"open": "08:00", "close": "17:00"},
            "sunday": "closed",
        },
        "social_links": {"instagram": "https://instagram.com/shantellsglow"},
        "tags": ["Hair", "Nails", "Skincare", "Braiding", "Walk-Ins Welcome"],
    },
    {
        "owner_email": "owner3@test.com",
        "category_slug": "construction-trades",
        "name": "Moss Construction & Renovations",
        "slug": "moss-construction-renovations",
        "short_description": "Residential and commercial construction, renovations, and repairs.",
        "description": "Moss Construction has been building and renovating homes across New Providence for 12 years. From kitchen remodels to full ground-up builds, we handle projects of every size with licensed tradesmen and quality materials. Free estimates provided.",
        "phone": "242-555-3001",
        "email": "derek@mossconstruction.com",
        "address_line1": "31 Yamacraw Hill Road",
        "settlement": "Yamacraw",
        "status": BusinessStatus.approved,
        "is_featured": True,
        "operating_hours": {
            "monday": {"open": "07:00", "close": "17:00"},
            "tuesday": {"open": "07:00", "close": "17:00"},
            "wednesday": {"open": "07:00", "close": "17:00"},
            "thursday": {"open": "07:00", "close": "17:00"},
            "friday": {"open": "07:00", "close": "16:00"},
            "saturday": {"open": "08:00", "close": "12:00"},
            "sunday": "closed",
        },
        "tags": ["Renovations", "New Builds", "Roofing", "Free Estimates"],
    },
    {
        "owner_email": "owner3@test.com",
        "category_slug": "electrical-plumbing",
        "name": "Moss Electrical Services",
        "slug": "moss-electrical-services",
        "short_description": "Licensed electrician for residential and commercial wiring.",
        "description": "Need an electrician you can trust? Moss Electrical handles panel upgrades, new construction wiring, ceiling fan installation, troubleshooting, and generator hookups. Fully licensed and insured.",
        "phone": "242-555-3002",
        "email": "electrical@mossconstruction.com",
        "address_line1": "31 Yamacraw Hill Road",
        "settlement": "Yamacraw",
        "status": BusinessStatus.approved,
        "is_featured": False,
        "operating_hours": {
            "monday": {"open": "07:00", "close": "17:00"},
            "tuesday": {"open": "07:00", "close": "17:00"},
            "wednesday": {"open": "07:00", "close": "17:00"},
            "thursday": {"open": "07:00", "close": "17:00"},
            "friday": {"open": "07:00", "close": "16:00"},
            "saturday": "closed",
            "sunday": "closed",
        },
        "tags": ["Electrical", "Generator", "Panel Upgrades", "Licensed"],
    },
    {
        "owner_email": "owner4@test.com",
        "category_slug": "technology-it",
        "name": "Tamika's Tech Repair",
        "slug": "tamikas-tech-repair",
        "short_description": "Phone, laptop, and tablet repairs. Same-day service available.",
        "description": "Cracked screen? Slow laptop? We fix iPhones, Samsung, MacBooks, Windows laptops, and tablets. Most repairs completed same day. We also sell refurbished devices and accessories.",
        "phone": "242-555-4001",
        "email": "tamika@techrepair242.com",
        "address_line1": "55 Fox Hill Road",
        "settlement": "Yamacraw",
        "status": BusinessStatus.pending_review,
        "is_featured": False,
        "operating_hours": {
            "monday": {"open": "09:00", "close": "18:00"},
            "tuesday": {"open": "09:00", "close": "18:00"},
            "wednesday": {"open": "09:00", "close": "18:00"},
            "thursday": {"open": "09:00", "close": "18:00"},
            "friday": {"open": "09:00", "close": "18:00"},
            "saturday": {"open": "10:00", "close": "15:00"},
            "sunday": "closed",
        },
        "tags": ["Phone Repair", "Laptop Repair", "Same-Day Service"],
    },
    # ── Contractors ────────────────────────────────────────────────────
    {
        "owner_email": "contractor1@test.com",
        "category_slug": "construction-trades",
        "name": "Bain Roofing & Waterproofing",
        "slug": "bain-roofing-waterproofing",
        "short_description": "Government-contracted roofing specialist for residential and public buildings.",
        "description": "Ricardo Bain has over 15 years of experience in roofing and waterproofing. Awarded multiple government contracts for school and public facility roof repairs across New Providence. Licensed, insured, and known for quality workmanship and on-time delivery.",
        "phone": "242-555-4101",
        "email": "ricardo@bainroofing.com",
        "address_line1": "9 Yamacraw Beach Road",
        "settlement": "Yamacraw",
        "status": BusinessStatus.approved,
        "is_featured": True,
        "listing_type": "contractor",
        "operating_hours": {
            "monday": {"open": "07:00", "close": "17:00"},
            "tuesday": {"open": "07:00", "close": "17:00"},
            "wednesday": {"open": "07:00", "close": "17:00"},
            "thursday": {"open": "07:00", "close": "17:00"},
            "friday": {"open": "07:00", "close": "15:00"},
            "saturday": "closed",
            "sunday": "closed",
        },
        "tags": ["Roofing", "Waterproofing", "Government Contracts", "Licensed"],
    },
    {
        "owner_email": "contractor2@test.com",
        "category_slug": "cleaning-services",
        "name": "Wells Environmental Services",
        "slug": "wells-environmental-services",
        "short_description": "Commercial cleaning and sanitation contractor for government and private facilities.",
        "description": "Wells Environmental Services provides deep cleaning, sanitation, and janitorial services for government offices, schools, clinics, and private businesses. Our team is trained in hazardous material handling and uses eco-friendly products. Currently serving 12 government contracts across Nassau.",
        "phone": "242-555-4201",
        "email": "patricia@wellsenvironmental.com",
        "website": "https://wellsenvironmental.com",
        "address_line1": "22 Fox Hill Road",
        "settlement": "Yamacraw",
        "status": BusinessStatus.approved,
        "is_featured": True,
        "listing_type": "contractor",
        "operating_hours": {
            "monday": {"open": "06:00", "close": "18:00"},
            "tuesday": {"open": "06:00", "close": "18:00"},
            "wednesday": {"open": "06:00", "close": "18:00"},
            "thursday": {"open": "06:00", "close": "18:00"},
            "friday": {"open": "06:00", "close": "18:00"},
            "saturday": {"open": "07:00", "close": "13:00"},
            "sunday": "closed",
        },
        "social_links": {"facebook": "https://facebook.com/wellsenvironmental"},
        "tags": ["Commercial Cleaning", "Sanitation", "Government Contracts", "Eco-Friendly"],
    },
    {
        "owner_email": "contractor3@test.com",
        "category_slug": "landscaping-gardening",
        "name": "Cartwright Landscaping & Grounds",
        "slug": "cartwright-landscaping-grounds",
        "short_description": "Professional landscaping and grounds maintenance for public parks and private estates.",
        "description": "Anthony Cartwright and his team of 8 maintain parks, school grounds, and private properties across the Yamacraw constituency. Services include lawn mowing, tree trimming, irrigation system installation, and full landscape design. Holder of 3 active government maintenance contracts.",
        "phone": "242-555-4301",
        "email": "anthony@cartwrightlandscaping.com",
        "address_line1": "44 Prince Charles Drive",
        "settlement": "Yamacraw",
        "status": BusinessStatus.approved,
        "is_featured": True,
        "listing_type": "contractor",
        "operating_hours": {
            "monday": {"open": "06:30", "close": "16:30"},
            "tuesday": {"open": "06:30", "close": "16:30"},
            "wednesday": {"open": "06:30", "close": "16:30"},
            "thursday": {"open": "06:30", "close": "16:30"},
            "friday": {"open": "06:30", "close": "15:00"},
            "saturday": "closed",
            "sunday": "closed",
        },
        "tags": ["Landscaping", "Grounds Maintenance", "Tree Trimming", "Government Contracts", "Irrigation"],
    },
]

# ── Service Requests (inquiries) ───────────────────────────────────────────

TEST_INQUIRIES = [
    {
        "business_slug": "island-flavors-kitchen",
        "user_email": "user1@test.com",
        "sender_name": "James Knowles",
        "sender_email": "user1@test.com",
        "sender_phone": "242-555-0301",
        "subject": "Catering for birthday party",
        "message": "Hi, I'm planning a birthday party for about 40 people on April 12th. Could you provide a catering menu and pricing? We'd love conch fritters, cracked lobster, and peas & rice. Thank you!",
        "status": ServiceRequestStatus.open,
    },
    {
        "business_slug": "island-flavors-kitchen",
        "user_email": "user2@test.com",
        "sender_name": "Crystal Bethel",
        "sender_email": "user2@test.com",
        "subject": "Do you deliver?",
        "message": "Good afternoon. Do you offer delivery to the Yamacraw Beach area? I'd like to order lunch for my office (about 8 people) every Friday. Thanks.",
        "status": ServiceRequestStatus.replied,
        "owner_reply": "Hi Crystal! Yes, we deliver to Yamacraw Beach. For office orders of 8+, we offer a 10% discount. Call us at 242-555-1001 to set up a recurring Friday order. Looking forward to serving you!",
        "replied_at": NOW - timedelta(days=1),
    },
    {
        "business_slug": "shantells-glow-studio",
        "user_email": "user2@test.com",
        "sender_name": "Crystal Bethel",
        "sender_email": "user2@test.com",
        "subject": "Bridal party appointments",
        "message": "Hello Shantell! I'm getting married in May and would love to book hair and nails for myself and 4 bridesmaids. Do you do bridal packages? What dates do you have available in early May?",
        "status": ServiceRequestStatus.read,
    },
    {
        "business_slug": "moss-construction-renovations",
        "user_email": "user1@test.com",
        "sender_name": "James Knowles",
        "sender_email": "user1@test.com",
        "sender_phone": "242-555-0301",
        "subject": "Kitchen renovation estimate",
        "message": "Good day Mr. Moss. I'm looking to renovate my kitchen - new countertops, cabinets, and flooring. The kitchen is about 12x14 feet. Could you come by for a free estimate? I'm on Yamacraw Hill Road.",
        "status": ServiceRequestStatus.replied,
        "owner_reply": "Good day James! Absolutely, I'd be happy to come by for a free estimate. I have availability this Thursday or Friday afternoon. Please call me at 242-555-3001 so we can confirm a time. Looking forward to seeing the space.",
        "replied_at": NOW - timedelta(days=3),
    },
    {
        "business_slug": "moss-electrical-services",
        "user_email": None,
        "sender_name": "Robert Stuart",
        "sender_email": "rstuart@gmail.com",
        "sender_phone": "242-555-9999",
        "subject": "Generator hookup",
        "message": "I just purchased a 10kw generator and need it professionally connected to my panel with a transfer switch. Can you handle this? What would it cost approximately?",
        "status": ServiceRequestStatus.open,
    },
    {
        "business_slug": "bain-roofing-waterproofing",
        "user_email": "user1@test.com",
        "sender_name": "James Knowles",
        "sender_email": "user1@test.com",
        "sender_phone": "242-555-0301",
        "subject": "Roof repair estimate",
        "message": "Good day Mr. Bain. I have a leak in my roof that gets worse every time it rains. The house is a single-story concrete block home. Could you come take a look and give me an estimate?",
        "status": ServiceRequestStatus.open,
    },
    {
        "business_slug": "cartwright-landscaping-grounds",
        "user_email": None,
        "sender_name": "Ministry of Works",
        "sender_email": "procurement@mow.gov.bs",
        "subject": "Grounds maintenance tender",
        "message": "We are seeking quotes for grounds maintenance at Yamacraw Primary School for the 2026-2027 fiscal year. Please submit your proposal by April 15th. Scope includes weekly lawn mowing, monthly tree trimming, and seasonal planting.",
        "status": ServiceRequestStatus.read,
    },
]


def seed_test_data():
    db = SessionLocal()
    hashed = hash_password(PASSWORD)

    try:
        # Check if test data already exists
        existing = db.query(User).filter(User.email == "owner1@test.com").first()
        if existing:
            print("Test data already seeded. Skipping.")
            return

        # ── Create users ───────────────────────────────────────────────
        user_map = {}
        for u in TEST_USERS:
            user = User(
                email=u["email"],
                hashed_password=hashed,
                first_name=u["first_name"],
                last_name=u["last_name"],
                phone=u.get("phone"),
                role=u["role"],
                status=UserStatus.active,
                email_verified=True,
            )
            db.add(user)
            db.flush()
            user_map[u["email"]] = user
            print(f"  Created user: {u['email']} ({u['role'].value})")

        # ── Get category map ───────────────────────────────────────────
        categories = {c.slug: c for c in db.query(Category).all()}

        # ── Create businesses ──────────────────────────────────────────
        biz_map = {}
        admin_user = db.query(User).filter(User.email == "admin@yamacrawbusinessportal.com").first()

        for b in TEST_BUSINESSES:
            owner = user_map[b["owner_email"]]
            cat = categories.get(b["category_slug"])
            if not cat:
                print(f"  WARNING: Category '{b['category_slug']}' not found, skipping {b['name']}")
                continue

            biz = Business(
                owner_id=owner.id,
                category_id=cat.id,
                name=b["name"],
                slug=b["slug"],
                short_description=b["short_description"],
                description=b["description"],
                phone=b.get("phone"),
                email=b.get("email"),
                website=b.get("website"),
                address_line1=b.get("address_line1"),
                island="New Providence",
                settlement=b.get("settlement", "Yamacraw"),
                status=b["status"],
                is_featured=b.get("is_featured", False),
                listing_type=ListingType(b["listing_type"]) if b.get("listing_type") else ListingType.business,
                operating_hours=b.get("operating_hours"),
                social_links=b.get("social_links"),
                approved_at=NOW - timedelta(days=7) if b["status"] == BusinessStatus.approved else None,
                approved_by=admin_user.id if b["status"] == BusinessStatus.approved and admin_user else None,
            )
            db.add(biz)
            db.flush()
            biz_map[b["slug"]] = biz

            # Tags
            for tag_text in b.get("tags", []):
                db.add(BusinessTag(business_id=biz.id, tag=tag_text))

            # View stats for approved businesses
            if b["status"] == BusinessStatus.approved:
                import random
                db.add(BusinessViewStats(
                    business_id=biz.id,
                    view_count=random.randint(15, 200),
                    last_viewed_at=NOW - timedelta(hours=random.randint(1, 48)),
                ))

            print(f"  Created business: {b['name']} [{b['status'].value}]")

        # ── Create inquiries ───────────────────────────────────────────
        for inq in TEST_INQUIRIES:
            biz = biz_map.get(inq["business_slug"])
            if not biz:
                continue

            user = user_map.get(inq["user_email"]) if inq["user_email"] else None

            sr = ServiceRequest(
                business_id=biz.id,
                user_id=user.id if user else None,
                sender_name=inq["sender_name"],
                sender_email=inq["sender_email"],
                sender_phone=inq.get("sender_phone"),
                subject=inq["subject"],
                message=inq["message"],
                status=inq["status"],
                owner_reply=inq.get("owner_reply"),
                replied_at=inq.get("replied_at"),
                ip_address="127.0.0.1",
            )
            db.add(sr)
            print(f"  Created inquiry: \"{inq['subject']}\" -> {biz.name} [{inq['status'].value}]")

        db.commit()
        print("\nTest data seeded successfully!")

    except Exception as e:
        db.rollback()
        print(f"Error seeding test data: {e}")
        raise
    finally:
        db.close()


def remove_test_data():
    """Remove all test data (users with @test.com emails and their businesses/inquiries)."""
    db = SessionLocal()
    try:
        test_users = db.query(User).filter(User.email.like("%@test.com")).all()
        if not test_users:
            print("No test data found.")
            return

        for user in test_users:
            db.delete(user)
            print(f"  Deleted user: {user.email} (cascades businesses & inquiries)")

        db.commit()
        print("Test data removed.")
    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--remove", action="store_true", help="Remove test data instead of seeding")
    args = parser.parse_args()

    if args.remove:
        print("Removing test data...")
        remove_test_data()
    else:
        print("Seeding test data...")
        seed_test_data()
