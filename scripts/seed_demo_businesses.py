"""Seed demo/showcase businesses for all categories.

All listings created by this script are marked ``is_demo=True`` so the system
admin can remove them in a single click from the admin portal (or via the
companion ``--remove`` flag below).

Usage:
    python -m scripts.seed_demo_businesses           # create
    python -m scripts.seed_demo_businesses --remove  # wipe demo listings

Notes:
- All businesses are located in the Yamacraw / Fox Hill area of New Providence.
- Logos are served from ui-avatars.com (stable permanent URLs, no API key).
- A shared ``demo@yamacrawbusinessportal.com`` owner ties the listings back to
  a single account for auditability. Password: Demo@YBP2026!
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.business import Business, BusinessTag, BusinessViewStats
from app.models.category import Category
from app.models.enums import BusinessStatus, ListingType, UserRole, UserStatus
from app.models.user import User


NOW = datetime.now(timezone.utc)

DEMO_OWNER_EMAIL = "demo@yamacrawbusinessportal.com"
DEMO_OWNER_PASSWORD = "Demo@YBP2026!"


# -- Logo helper ------------------------------------------------------------

def _logo(name: str, bg: str) -> str:
    """Build a ui-avatars URL with a bold initial-based mark."""
    return (
        "https://ui-avatars.com/api/"
        f"?name={quote(name)}"
        f"&background={bg}"
        "&color=fff"
        "&size=400"
        "&bold=true"
        "&font-size=0.42"
        "&format=png"
    )


# Bahamian-leaning palette (flag + sea + sand)
PALETTE = {
    "aqua": "00A79D",
    "teal": "0E7C86",
    "ocean": "0369A1",
    "sky": "0284C7",
    "navy": "1E3A8A",
    "coral": "EF5A3C",
    "sunset": "F97316",
    "gold": "D97706",
    "mango": "F59E0B",
    "rose": "E11D48",
    "fuchsia": "C026D3",
    "forest": "15803D",
    "lime": "65A30D",
    "slate": "475569",
    "charcoal": "1F2937",
}


# -- Demo listings ----------------------------------------------------------
# Each listing uses a Bahamian-flavored name + address in the Yamacraw area.
# All listings are approved and visible in the directory.

DEMO_LISTINGS = [
    # ── Restaurants & Food ─────────────────────────────────────────────
    {
        "category_slug": "restaurants-food",
        "name": "Conch Shack Yamacraw",
        "color": "coral",
        "short_description": "Fresh conch salad, cracked conch, and ice-cold Kalik with an East End view.",
        "description": "A Yamacraw Beach staple for over seven years. Our conch is caught daily and prepped in front of you—just the way locals like it. Pair a bowl of conch salad with fish fingers, scorched conch, or a piping-hot bowl of boil fish on Saturday mornings.",
        "phone": "242-555-1101",
        "email": "orders@conchshackyamacraw.com",
        "address_line1": "14 Yamacraw Beach Road",
        "tags": ["Bahamian Food", "Seafood", "Conch", "Beachside", "Family-Friendly"],
        "is_featured": True,
    },
    {
        "category_slug": "restaurants-food",
        "name": "Mama Rolle's Bakery",
        "color": "gold",
        "short_description": "Coconut tarts, guava duff and hot Johnny cake baked fresh each morning.",
        "description": "Three generations of Bahamian baking. Mama Rolle's has supplied Yamacraw families with bread, rock cakes, benny cakes, and the island's finest coconut tarts since 1998. Custom cakes available for weddings, showers and birthdays.",
        "phone": "242-555-1102",
        "email": "hello@mamarollesbakery.bs",
        "address_line1": "27 Prince Charles Drive",
        "tags": ["Bakery", "Bahamian Desserts", "Custom Cakes", "Coconut Tarts"],
    },
    # ── Auto Services ──────────────────────────────────────────────────
    {
        "category_slug": "auto-services",
        "name": "East End Auto Works",
        "color": "navy",
        "short_description": "Full-service garage: diagnostics, AC repair, brakes, and suspension.",
        "description": "East End Auto Works has been keeping Yamacraw commuters on the road for 12 years. Certified mechanics, same-day service on most repairs, and OEM parts for Japanese and German vehicles. Free pickup within a 5-mile radius.",
        "phone": "242-555-1201",
        "email": "service@eastendauto.bs",
        "address_line1": "88 Fox Hill Road",
        "tags": ["Mechanic", "AC Repair", "Brakes", "Diagnostics", "Same-Day"],
    },
    {
        "category_slug": "auto-services",
        "name": "Smith's Car Wash & Detail",
        "color": "sky",
        "short_description": "Hand wash, interior detail and ceramic coating for all vehicle sizes.",
        "description": "Hand-wash only, no automated brushes. We carry wax, interior shampoo, leather conditioning and full ceramic packages. Appointments preferred for detail jobs; drive-through wash available 7 days a week.",
        "phone": "242-555-1202",
        "email": "info@smithscarwash.com",
        "address_line1": "3 Yamacraw Road",
        "tags": ["Hand Wash", "Detailing", "Ceramic Coating", "Interior Shampoo"],
    },
    # ── Home Services ──────────────────────────────────────────────────
    {
        "category_slug": "home-services",
        "name": "Bahama Home Solutions",
        "color": "teal",
        "short_description": "Handyman, minor repairs, assembly and home organization.",
        "description": "From door hinges to IKEA assembly, Bahama Home Solutions tackles the small jobs that contractors won't. One-hour minimum, flat hourly rate, and all our handymen are insured and background-checked.",
        "phone": "242-555-1301",
        "email": "book@bahamahome.bs",
        "address_line1": "56 Yamacraw Hill Road",
        "tags": ["Handyman", "Repairs", "Assembly", "Insured"],
        "is_featured": True,
    },
    {
        "category_slug": "home-services",
        "name": "Sea Breeze AC & Appliance",
        "color": "aqua",
        "short_description": "AC servicing, fridge repair and washing-machine diagnostics.",
        "description": "We service all major brands of split-type AC, refrigerators and laundry appliances. Preventive maintenance plans start at $60/quarter. Emergency weekend calls available—don't sit in the heat for the weekend.",
        "phone": "242-555-1302",
        "email": "seabreeze.ac@bahamas.email",
        "address_line1": "11 Sea Breeze Lane",
        "tags": ["AC Service", "Appliance Repair", "Maintenance Plans"],
    },
    # ── Beauty & Wellness ──────────────────────────────────────────────
    {
        "category_slug": "beauty-wellness",
        "name": "Hibiscus Hair Lounge",
        "color": "rose",
        "short_description": "Natural hair, silk presses, braids and bridal styling.",
        "description": "A celebration of Bahamian hair. Our stylists specialize in protective styles—knotless braids, locs, feed-ins—plus relaxers, silk presses and bridal party bookings. Kids' cornrows every Saturday.",
        "phone": "242-555-1401",
        "email": "bookings@hibiscuslounge.bs",
        "address_line1": "9 Yamacraw Road, Suite B",
        "tags": ["Natural Hair", "Braids", "Bridal", "Walk-Ins Welcome"],
        "is_featured": True,
    },
    {
        "category_slug": "beauty-wellness",
        "name": "Serenity Nail Bar",
        "color": "fuchsia",
        "short_description": "Gel manicures, spa pedicures and nail art in a calm, tropical studio.",
        "description": "Sanitized tools, licensed nail technicians, and a 20-page design catalog. Gel, polygel, acrylic overlays, and chrome finishes. Pedicure chairs face our indoor garden wall.",
        "phone": "242-555-1402",
        "email": "hello@serenitynailbar.bs",
        "address_line1": "41 Fox Hill Road",
        "tags": ["Gel Manicure", "Pedicure", "Nail Art", "Sanitized"],
    },
    # ── Construction & Trades ──────────────────────────────────────────
    {
        "category_slug": "construction-trades",
        "name": "Albury Building Co.",
        "color": "slate",
        "short_description": "Residential builds, hurricane-rated roofs, and concrete work.",
        "description": "Three generations of Bahamian builders. Albury Building Co. handles ground-up residential construction, hurricane-rated roofing retrofits, and block-and-beam foundations. Licensed and bonded for projects up to $2M.",
        "phone": "242-555-1501",
        "email": "projects@alburybuilding.bs",
        "address_line1": "102 Gladstone Road",
        "tags": ["New Construction", "Roofing", "Concrete", "Licensed", "Bonded"],
    },
    {
        "category_slug": "construction-trades",
        "name": "Island Stone Masonry",
        "color": "charcoal",
        "short_description": "Natural stone walls, driveways, and decorative masonry.",
        "description": "Hand-laid keystone, flagstone and cut-limestone features. We cut and source locally so your project reflects Bahamian craft. Driveways, boundary walls, patios and fireplace surrounds.",
        "phone": "242-555-1502",
        "email": "masonry@islandstone.bs",
        "address_line1": "61 Yamacraw Hill Road",
        "tags": ["Masonry", "Stone Walls", "Driveways", "Custom"],
    },
    # ── Cleaning Services ──────────────────────────────────────────────
    {
        "category_slug": "cleaning-services",
        "name": "Pristine Island Cleaners",
        "color": "aqua",
        "short_description": "Deep-cleans, weekly maid service and move-out scrubs.",
        "description": "Bonded team, eco-friendly supplies, and a satisfaction guarantee. We do weekly/bi-weekly maintenance cleans, move-in/move-out deep cleans, and post-construction cleanups. Airbnb turnovers welcome.",
        "phone": "242-555-1601",
        "email": "clean@pristineisland.bs",
        "address_line1": "22 Prince Charles Drive",
        "tags": ["Residential", "Airbnb Turnover", "Eco-Friendly", "Bonded"],
    },
    {
        "category_slug": "cleaning-services",
        "name": "Yamacraw Window & Power Wash",
        "color": "sky",
        "short_description": "Window cleaning, driveway pressure-washing and gutter flush.",
        "description": "Salt air, gone. We pressure-wash driveways, patios and pool decks, plus interior/exterior window packages for homes up to three storeys. Quarterly maintenance plans available.",
        "phone": "242-555-1602",
        "email": "pw@yamacrawwindow.bs",
        "address_line1": "5 Yamacraw Beach Road",
        "tags": ["Windows", "Pressure Washing", "Gutters", "Maintenance"],
    },
    # ── Electrical & Plumbing ──────────────────────────────────────────
    {
        "category_slug": "electrical-plumbing",
        "name": "Bright Spark Electric",
        "color": "mango",
        "short_description": "Licensed electrician: panels, generators, ceiling fans, EV chargers.",
        "description": "Over 20 years wiring homes from Coral Harbour to East End. We handle panel upgrades, generator transfer switches, EV charger installs, ceiling fans and landscape lighting. Written estimates within 24 hours.",
        "phone": "242-555-1701",
        "email": "info@brightspark.bs",
        "address_line1": "77 Fox Hill Road",
        "tags": ["Electrical", "Generators", "EV Chargers", "Licensed"],
        "is_featured": True,
    },
    {
        "category_slug": "electrical-plumbing",
        "name": "Clear Flow Plumbing",
        "color": "ocean",
        "short_description": "Emergency leak repair, water-heater install and re-piping.",
        "description": "24/7 emergency service for burst pipes, sewer backups and failed water heaters. We also handle new-build rough-ins and whole-house re-pipe projects. Fully insured.",
        "phone": "242-555-1702",
        "email": "dispatch@clearflow.bs",
        "address_line1": "18 Yamacraw Road",
        "tags": ["Plumbing", "Emergency", "Water Heaters", "Re-Piping"],
    },
    # ── Landscaping & Gardening ────────────────────────────────────────
    {
        "category_slug": "landscaping-gardening",
        "name": "Palm & Frond Landscaping",
        "color": "forest",
        "short_description": "Weekly lawn care, tree trimming and native plant design.",
        "description": "We design and maintain gardens that thrive in Bahamian climate. Native plantings, irrigation systems, mulch, and full weekly maintenance. Monthly contracts from $120.",
        "phone": "242-555-1801",
        "email": "grow@palmandfrond.bs",
        "address_line1": "66 Prince Charles Drive",
        "tags": ["Landscaping", "Lawn Care", "Irrigation", "Native Plants"],
    },
    {
        "category_slug": "landscaping-gardening",
        "name": "Coconut Grove Tree Service",
        "color": "lime",
        "short_description": "Tree trimming, hurricane prep and stump grinding.",
        "description": "Certified arborists with full bucket-truck service. We thin canopies before hurricane season, remove damaged limbs, and grind stumps flush. Cleanup and haul-away included in every quote.",
        "phone": "242-555-1802",
        "email": "trees@coconutgrove.bs",
        "address_line1": "8 Yamacraw Hill Road",
        "tags": ["Tree Service", "Stump Grinding", "Hurricane Prep", "Arborist"],
    },
    # ── Technology & IT ────────────────────────────────────────────────
    {
        "category_slug": "technology-it",
        "name": "BlueNet IT Support",
        "color": "ocean",
        "short_description": "Managed IT, Wi-Fi installs and small-business cloud migration.",
        "description": "We're the IT department for 40+ Nassau businesses. Monthly flat-rate support, Microsoft 365 migration, network security audits and structured cabling. Remote help-desk plus on-site visits.",
        "phone": "242-555-1901",
        "email": "support@bluenet.bs",
        "address_line1": "14 East Bay Street",
        "tags": ["Managed IT", "Wi-Fi", "Microsoft 365", "Networking"],
    },
    {
        "category_slug": "technology-it",
        "name": "Island Device Repair",
        "color": "charcoal",
        "short_description": "Phone screen, laptop and tablet repairs — walk-in or mail-in.",
        "description": "Cracked iPhone screens replaced in 45 minutes. MacBook battery swaps, logic-board repair, tablet digitizer replacement, and data recovery. 90-day warranty on every repair.",
        "phone": "242-555-1902",
        "email": "fix@islanddevice.bs",
        "address_line1": "33 Prince Charles Drive",
        "tags": ["Phone Repair", "Laptop", "Data Recovery", "Walk-In"],
    },
    # ── Professional Services ──────────────────────────────────────────
    {
        "category_slug": "professional-services",
        "name": "Ferguson & Knowles Accounting",
        "color": "navy",
        "short_description": "Bookkeeping, VAT filing and small-business tax compliance.",
        "description": "A Bahamian-owned firm handling bookkeeping, payroll, VAT and business-license renewals. Monthly packages for sole traders, partnerships and small corporations. QuickBooks Certified ProAdvisors on staff.",
        "phone": "242-555-2001",
        "email": "inquiry@fergusonknowles.bs",
        "address_line1": "45 Yamacraw Road",
        "tags": ["Accounting", "Bookkeeping", "VAT", "Payroll"],
    },
    {
        "category_slug": "professional-services",
        "name": "Rolle Legal Chambers",
        "color": "charcoal",
        "short_description": "Conveyancing, wills, corporate and immigration law.",
        "description": "Boutique Bahamian law firm established 2009. Real-estate conveyancing, probate, wills & trusts, corporate formation and personal injury. Initial consultations are complimentary.",
        "phone": "242-555-2002",
        "email": "chambers@rollelegal.bs",
        "address_line1": "2 East Bay Street",
        "tags": ["Attorney", "Conveyancing", "Wills", "Corporate Law"],
    },
    # ── Education & Tutoring ───────────────────────────────────────────
    {
        "category_slug": "education-tutoring",
        "name": "Yamacraw Learning Hub",
        "color": "sky",
        "short_description": "After-school tutoring for primary and BGCSE prep for high schoolers.",
        "description": "Small-group tutoring for grades 3–12. Math, English, Spanish, Biology and BGCSE exam prep. Our tutors are certified Bahamian teachers with proven track records at leading schools.",
        "phone": "242-555-2101",
        "email": "enroll@yamacrawlearning.bs",
        "address_line1": "19 Fox Hill Road",
        "tags": ["Tutoring", "BGCSE Prep", "After School", "Math & English"],
    },
    {
        "category_slug": "education-tutoring",
        "name": "Coral Reef Music Academy",
        "color": "fuchsia",
        "short_description": "Piano, guitar, steel pan and voice lessons for all ages.",
        "description": "Weekly one-on-one instruction in a bright, welcoming studio. Annual recitals, ABRSM exam prep and adult beginners welcome. Group steel-pan classes on Saturday mornings.",
        "phone": "242-555-2102",
        "email": "music@coralreefacademy.bs",
        "address_line1": "12 Yamacraw Beach Road",
        "tags": ["Music Lessons", "Piano", "Steel Pan", "ABRSM"],
    },
    # ── Health & Medical ───────────────────────────────────────────────
    {
        "category_slug": "health-medical",
        "name": "Yamacraw Family Clinic",
        "color": "rose",
        "short_description": "General practice, immunizations and annual physicals.",
        "description": "Dr. Cartwright and Dr. Minnis run a full family practice serving the Yamacraw constituency. Same-day sick visits, annual physicals, school forms, and preventive care. NIB accepted.",
        "phone": "242-555-2201",
        "email": "appointments@yamacrawfamily.bs",
        "address_line1": "31 Yamacraw Road",
        "tags": ["Family Medicine", "Immunizations", "NIB Accepted"],
    },
    {
        "category_slug": "health-medical",
        "name": "Sea Breeze Physiotherapy",
        "color": "teal",
        "short_description": "Sports injury rehab, post-surgical therapy and dry needling.",
        "description": "Chartered physiotherapists offering sports rehabilitation, post-surgical recovery, chronic pain management, and dry needling. Equipped with full gym, ultrasound and TENS therapy.",
        "phone": "242-555-2202",
        "email": "clinic@seabreezephysio.bs",
        "address_line1": "7 Sea Breeze Lane",
        "tags": ["Physiotherapy", "Sports Rehab", "Post-Surgical", "Dry Needling"],
    },
    # ── Retail & Shopping ──────────────────────────────────────────────
    {
        "category_slug": "retail-shopping",
        "name": "Straw Market Revival",
        "color": "mango",
        "short_description": "Handwoven straw bags, vendor goods and Androsia fabrics.",
        "description": "A boutique champion of Bahamian craft. Androsia batik, handwoven straw accessories, local jams, hot sauces, and art from island painters. We stock small-batch Bahamian makers only.",
        "phone": "242-555-2301",
        "email": "shop@strawrevival.bs",
        "address_line1": "14 Yamacraw Road",
        "tags": ["Bahamian Made", "Crafts", "Androsia", "Gifts"],
    },
    {
        "category_slug": "retail-shopping",
        "name": "Kite + Tide Boutique",
        "color": "coral",
        "short_description": "Swimwear, beach caftans and resort-style accessories.",
        "description": "Curated beachwear from Caribbean and Bahamian designers, plus swimwear lines for every body type. Private shopping appointments and bridesmaid swim fittings available.",
        "phone": "242-555-2302",
        "email": "hello@kiteandtide.bs",
        "address_line1": "77 Prince Charles Drive",
        "tags": ["Boutique", "Swimwear", "Caftans", "Resort Wear"],
    },
    # ── Events & Entertainment ─────────────────────────────────────────
    {
        "category_slug": "events-entertainment",
        "name": "Island Nights Entertainment",
        "color": "fuchsia",
        "short_description": "DJs, steel-pan bands and MC services for weddings and parties.",
        "description": "A roster of 12 DJs, two live steel-pan bands, and two professional MCs. We've worked Atlantis, Baha Mar, and hundreds of private Yamacraw weddings and birthdays. Full sound and lighting packages.",
        "phone": "242-555-2401",
        "email": "book@islandnights.bs",
        "address_line1": "23 Yamacraw Hill Road",
        "tags": ["DJ", "Steel Pan", "MC", "Weddings", "Sound & Lighting"],
    },
    {
        "category_slug": "events-entertainment",
        "name": "Bougainvillea Event Rentals",
        "color": "rose",
        "short_description": "Tent, table, chair, linen and décor rentals for private events.",
        "description": "Our warehouse stocks 40'x60' tents, farmhouse tables, chiavari chairs, 200+ linen colors, and custom floral arches. Full-service setup and breakdown included on packages over 50 guests.",
        "phone": "242-555-2402",
        "email": "rentals@bougainvillea.bs",
        "address_line1": "9 Fox Hill Road",
        "tags": ["Event Rentals", "Tents", "Tables", "Décor"],
    },
    # ── Transportation ─────────────────────────────────────────────────
    {
        "category_slug": "transportation",
        "name": "Island Shuttle Services",
        "color": "gold",
        "short_description": "Airport pickup, tour shuttles and event transportation.",
        "description": "14-passenger and 25-passenger shuttles with professional Bahamian drivers. LPIA pickups, wedding-party shuttles, cruise-day tours, and corporate transportation. Meet-and-greet signage included.",
        "phone": "242-555-2501",
        "email": "book@islandshuttle.bs",
        "address_line1": "1 Yamacraw Road",
        "tags": ["Airport Shuttle", "Tours", "Charter", "Professional Drivers"],
    },
    {
        "category_slug": "transportation",
        "name": "Lucaya Moving Co.",
        "color": "navy",
        "short_description": "Residential moves, packing and long-haul to Family Islands.",
        "description": "Two-man, four-man, and six-man crews. Bubble-wrap, pack-and-unpack service, and inter-island freight to Exuma, Eleuthera and Abaco. Fully insured, with in-house piano movers.",
        "phone": "242-555-2502",
        "email": "move@lucayamoving.bs",
        "address_line1": "47 Gladstone Road",
        "tags": ["Moving", "Packing", "Inter-Island", "Insured"],
    },
    # ── Pet Services ───────────────────────────────────────────────────
    {
        "category_slug": "pet-services",
        "name": "Paws on the Point Grooming",
        "color": "sunset",
        "short_description": "Dog grooming, nail trims and cat baths in a stress-free studio.",
        "description": "Certified groomers specializing in double-coated breeds, potcakes and rescues. We offer de-shedding treatments, teeth brushing and nail grinding. Same-day pickup window is 4 hours.",
        "phone": "242-555-2601",
        "email": "bookings@pawsonthepoint.bs",
        "address_line1": "18 Yamacraw Road",
        "tags": ["Grooming", "Dogs", "Cats", "Potcake Friendly"],
    },
    {
        "category_slug": "pet-services",
        "name": "Coral Cove Pet Sitting",
        "color": "lime",
        "short_description": "In-home pet sitting, dog walking and boarding alternative.",
        "description": "We come to your home so your dog or cat stays stress-free. Daily updates with photos, medication administration, and overnight stays available. Bonded, insured and pet CPR certified.",
        "phone": "242-555-2602",
        "email": "care@coralcovepets.bs",
        "address_line1": "5 Sea Breeze Lane",
        "tags": ["Pet Sitting", "Dog Walking", "Medication", "Insured"],
    },
    # ── Photography & Media ────────────────────────────────────────────
    {
        "category_slug": "photography-media",
        "name": "Junkanoo Lens Studio",
        "color": "charcoal",
        "short_description": "Wedding, editorial and commercial photography.",
        "description": "Bahamian-owned studio with a style that blends editorial cleanliness with island warmth. Destination weddings, family portraits, brand shoots, and aerial drone work.",
        "phone": "242-555-2701",
        "email": "studio@junkanoolens.bs",
        "address_line1": "21 East Bay Street",
        "tags": ["Weddings", "Editorial", "Drone", "Portraits"],
        "is_featured": True,
    },
    {
        "category_slug": "photography-media",
        "name": "Cayo Video Productions",
        "color": "slate",
        "short_description": "Corporate video, event coverage and social-media edits.",
        "description": "Full-service video team: 4K cameras, drone pilots, and an in-house editor. Explainer videos, event highlight reels, social-media shorts and wedding films delivered in 3 weeks.",
        "phone": "242-555-2702",
        "email": "production@cayovideo.bs",
        "address_line1": "30 Prince Charles Drive",
        "tags": ["Video Production", "Corporate", "Events", "Drone"],
    },
    # ── Financial Services ─────────────────────────────────────────────
    {
        "category_slug": "financial-services",
        "name": "Bahama Shield Insurance Brokers",
        "color": "forest",
        "short_description": "Home, auto, and commercial insurance across all Bahamian insurers.",
        "description": "Independent brokerage representing every major Bahamian insurer. We shop your renewal every year to keep premiums honest. Free policy reviews, and on-the-spot quote service.",
        "phone": "242-555-2801",
        "email": "quote@bahamashield.bs",
        "address_line1": "6 Yamacraw Road",
        "tags": ["Insurance", "Home", "Auto", "Commercial", "Broker"],
    },
    {
        "category_slug": "financial-services",
        "name": "Island Wealth Advisors",
        "color": "navy",
        "short_description": "Financial planning, retirement and investment advisory for Bahamians.",
        "description": "Fee-only fiduciary planners helping Bahamian professionals build retirement portfolios, plan estate transitions, and make smart decisions about business sale proceeds. Licensed SCB registrants.",
        "phone": "242-555-2802",
        "email": "advisors@islandwealth.bs",
        "address_line1": "14 Yamacraw Hill Road",
        "tags": ["Financial Planning", "Retirement", "Investing", "Licensed"],
    },
    # ── Other Services ─────────────────────────────────────────────────
    {
        "category_slug": "other-services",
        "name": "Coconut Copy & Print",
        "color": "mango",
        "short_description": "Printing, scanning, banners and notary services.",
        "description": "Walk-in print shop. Large-format banners, business cards, letterhead, school project posters, passport photos, and certified notary public on site. Same-day turnaround for most jobs.",
        "phone": "242-555-2901",
        "email": "print@coconutcopy.bs",
        "address_line1": "55 Fox Hill Road",
        "tags": ["Printing", "Banners", "Notary", "Passport Photos"],
    },
    # ── Contractors ────────────────────────────────────────────────────
    {
        "category_slug": "construction-trades",
        "name": "Pinder Roofing Contractors",
        "color": "charcoal",
        "short_description": "Hurricane-rated roofing for government and commercial contracts.",
        "description": "Pinder Roofing has held roofing contracts with three ministries and multiple private schools across New Providence. Metal, shingle and membrane systems — all hurricane-rated. Bonded to $5M.",
        "phone": "242-555-3101",
        "email": "bids@pinderroofing.bs",
        "address_line1": "12 Yamacraw Beach Road",
        "tags": ["Roofing", "Government Contracts", "Hurricane Rated", "Bonded"],
        "listing_type": "contractor",
        "is_featured": True,
    },
    {
        "category_slug": "electrical-plumbing",
        "name": "Voltaire Electrical Contractors",
        "color": "mango",
        "short_description": "Commercial electrical contractor — new builds and retrofits.",
        "description": "Voltaire is the electrical partner behind several government office retrofits and school expansions. Full BEC coordination, switchgear, fire-alarm integration, and emergency generators.",
        "phone": "242-555-3102",
        "email": "projects@voltaireelectric.bs",
        "address_line1": "88 Gladstone Road",
        "tags": ["Commercial Electrical", "Government Contracts", "Switchgear"],
        "listing_type": "contractor",
    },
    {
        "category_slug": "cleaning-services",
        "name": "Atlantic Facility Services",
        "color": "aqua",
        "short_description": "Commercial janitorial and facility-management contractor.",
        "description": "We run nightly cleaning crews for six banks, two ministries and three private schools. Bonded, uniformed staff with criminal-background screening. Seven-day service windows available.",
        "phone": "242-555-3103",
        "email": "contracts@atlanticfacility.bs",
        "address_line1": "22 Fox Hill Road",
        "tags": ["Commercial Cleaning", "Government Contracts", "Bonded"],
        "listing_type": "contractor",
        "is_featured": True,
    },
    {
        "category_slug": "landscaping-gardening",
        "name": "Green Crest Grounds Maintenance",
        "color": "forest",
        "short_description": "Grounds maintenance contractor for schools and public parks.",
        "description": "Green Crest services 14 public and private properties across New Providence. Weekly mowing, edging, hedge trimming and irrigation upkeep. 8-person crew with dedicated foreman per site.",
        "phone": "242-555-3104",
        "email": "greencrest@grounds.bs",
        "address_line1": "44 Prince Charles Drive",
        "tags": ["Grounds Maintenance", "Schools", "Parks", "Government Contracts"],
        "listing_type": "contractor",
    },
    {
        "category_slug": "construction-trades",
        "name": "Sawyer Civil Works",
        "color": "slate",
        "short_description": "Road works, drainage and culvert repair specialist.",
        "description": "Sawyer crews handle street-paving, storm-drain installation, and culvert replacements under Ministry of Works tenders. Full fleet of excavators, pavers and dump trucks. BPL coordinated.",
        "phone": "242-555-3105",
        "email": "civil@sawyerworks.bs",
        "address_line1": "102 Yamacraw Hill Road",
        "tags": ["Civil Works", "Paving", "Drainage", "Government Contracts"],
        "listing_type": "contractor",
    },
    {
        "category_slug": "professional-services",
        "name": "Dunmore Surveying & Mapping",
        "color": "navy",
        "short_description": "Licensed land surveyors and GIS mapping contractor.",
        "description": "Registered Bahamian land surveyors providing boundary surveys, topographic mapping, construction staking and GIS data products. Government-approved vendor list.",
        "phone": "242-555-3106",
        "email": "surveys@dunmoremapping.bs",
        "address_line1": "9 East Bay Street",
        "tags": ["Land Surveying", "GIS", "Boundary Surveys", "Licensed"],
        "listing_type": "contractor",
    },
]


# -- Helpers ----------------------------------------------------------------

def _slugify(name: str) -> str:
    import re

    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return f"{base}-demo"


def _default_hours():
    return {
        "monday": {"open": "08:00", "close": "17:00"},
        "tuesday": {"open": "08:00", "close": "17:00"},
        "wednesday": {"open": "08:00", "close": "17:00"},
        "thursday": {"open": "08:00", "close": "17:00"},
        "friday": {"open": "08:00", "close": "17:00"},
        "saturday": {"open": "09:00", "close": "14:00"},
        "sunday": "closed",
    }


# -- Seed / Remove ----------------------------------------------------------

def seed_demo():
    db = SessionLocal()
    try:
        # Demo owner
        owner = db.query(User).filter(User.email == DEMO_OWNER_EMAIL).first()
        if not owner:
            owner = User(
                email=DEMO_OWNER_EMAIL,
                hashed_password=hash_password(DEMO_OWNER_PASSWORD),
                first_name="Demo",
                last_name="Directory",
                phone="242-555-0000",
                role=UserRole.business_owner,
                status=UserStatus.active,
                email_verified=True,
            )
            db.add(owner)
            db.flush()
            print(f"Created demo owner: {DEMO_OWNER_EMAIL} / {DEMO_OWNER_PASSWORD}")
        else:
            print(f"Demo owner already exists: {DEMO_OWNER_EMAIL}")

        # Find an approving admin (any admin will do)
        admin_user = (
            db.query(User)
            .filter(User.role.in_([UserRole.admin, UserRole.system_admin]))
            .first()
        )

        categories = {c.slug: c for c in db.query(Category).all()}

        created = 0
        skipped = 0
        for entry in DEMO_LISTINGS:
            cat = categories.get(entry["category_slug"])
            if cat is None:
                print(f"  ! Category missing: {entry['category_slug']}  (skipping {entry['name']})")
                skipped += 1
                continue

            slug = _slugify(entry["name"])
            existing = db.query(Business).filter(Business.slug == slug).first()
            if existing:
                skipped += 1
                continue

            color_key = entry.get("color", "teal")
            color_hex = PALETTE.get(color_key, PALETTE["teal"])

            biz = Business(
                owner_id=owner.id,
                category_id=cat.id,
                name=entry["name"],
                slug=slug,
                short_description=entry["short_description"],
                description=entry["description"],
                phone=entry.get("phone"),
                email=entry.get("email"),
                website=entry.get("website"),
                address_line1=entry.get("address_line1"),
                island="New Providence",
                settlement="Yamacraw",
                logo_url=_logo(entry["name"], color_hex),
                status=BusinessStatus.approved,
                is_featured=entry.get("is_featured", False),
                is_demo=True,
                listing_type=ListingType(entry.get("listing_type", "business")),
                operating_hours=entry.get("operating_hours", _default_hours()),
                social_links=entry.get("social_links"),
                approved_at=NOW - timedelta(days=14),
                approved_by=admin_user.id if admin_user else None,
            )
            db.add(biz)
            db.flush()

            for tag_text in entry.get("tags", []):
                db.add(BusinessTag(business_id=biz.id, tag=tag_text))

            import random

            db.add(
                BusinessViewStats(
                    business_id=biz.id,
                    view_count=random.randint(20, 340),
                    last_viewed_at=NOW - timedelta(hours=random.randint(1, 72)),
                )
            )

            created += 1
            print(f"  + {entry['name']}  ({cat.slug})")

        db.commit()
        print(f"\nDemo seeding complete. Created: {created}, skipped: {skipped}.")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def remove_demo():
    db = SessionLocal()
    try:
        demos = db.query(Business).filter(Business.is_demo.is_(True)).all()
        if not demos:
            print("No demo listings found.")
            return
        for biz in demos:
            print(f"  - {biz.name}")
            db.delete(biz)

        owner = db.query(User).filter(User.email == DEMO_OWNER_EMAIL).first()
        if owner:
            remaining = db.query(Business).filter(Business.owner_id == owner.id).count()
            if remaining == 0:
                db.delete(owner)
                print(f"  - demo owner account {DEMO_OWNER_EMAIL}")

        db.commit()
        print(f"\nRemoved {len(demos)} demo listing(s).")
    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--remove", action="store_true", help="Remove all demo listings")
    args = parser.parse_args()

    if args.remove:
        remove_demo()
    else:
        seed_demo()
