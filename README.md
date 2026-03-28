# Yamacraw Business Portal - API

The backend API for the [Yamacraw Business Portal](https://yamacrawbusinessportal.com), a civic business directory connecting residents of the Yamacraw constituency in Nassau, The Bahamas with local businesses, government contractors, and service providers.

Sponsored by the Office of Minister Zane Enrico Lightbourne, Member of Parliament for Yamacraw.

## Tech Stack

- **FastAPI** with Python 3.11+
- **SQLAlchemy 2.0** ORM with PostgreSQL 16
- **Alembic** for database migrations
- **Pydantic v2** for request/response validation
- **JWT** dual-token authentication (access + refresh tokens)
- **passlib** + **bcrypt** for password hashing
- **slowapi** for rate limiting
- **Resend** for transactional email delivery
- **Pillow** + **python-magic** for image processing and validation
- **Cloudflare Turnstile** server-side CAPTCHA verification

## Features

- **Authentication**: Registration with email verification, login, JWT refresh, password reset, ToS acceptance
- **Business Listings**: Full CRUD with status lifecycle (draft, pending review, approved, rejected, suspended, archived)
- **Search**: Full-text search via PostgreSQL tsvector on business names, descriptions, and tags
- **Inquiry System**: Public inquiry forms with CAPTCHA, business owner reply flow, email notifications
- **Photo Uploads**: Image upload with MIME validation, EXIF stripping, and file size limits
- **Admin Moderation**: Listing approval/rejection queue, category management, flag resolution
- **User Management**: Role-based access control (public_user, business_owner, admin, system_admin)
- **Notifications**: In-app and email notifications for key events
- **Audit Logging**: Append-only audit trail of all administrative actions
- **Portal Feedback**: User ratings and comments about the portal itself
- **Reviews**: Business review and rating system with moderation
- **Rate Limiting**: Per-endpoint rate limits to prevent abuse

## Getting Started

### Prerequisites

- Python 3.11+
- PostgreSQL 16+

### Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -e ".[dev]"

# Copy environment template and configure
cp .env.example .env

# Run migrations
alembic upgrade head

# Seed initial data (categories, admin account)
python scripts/seed.py

# Start dev server
uvicorn app.main:app --reload --port 8000
```

### Environment Variables

Key variables (see `.env.example` for the full list):

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `JWT_SECRET_KEY` | Secret for signing JWT tokens |
| `CORS_ORIGINS` | Allowed frontend origins |
| `RESEND_API_KEY` | Resend API key for email delivery |
| `TURNSTILE_SECRET_KEY` | Cloudflare Turnstile secret |
| `UPLOAD_DIR` | Directory for uploaded files |

### Docker

The API runs as part of the full stack via Docker Compose (defined in the frontend repo):

```bash
cd ../yamacrawbusinessportal-frontend
docker compose up --build
```

## Project Structure

```
app/
  main.py              # FastAPI app, middleware, router mounting
  api/
    deps.py            # Dependency injection (auth, DB session)
    controllers/       # Route handlers
  core/
    config.py          # Settings via pydantic-settings
    security.py        # JWT and password utilities
    email.py           # Resend email client
    captcha.py         # Turnstile verification
  models/              # SQLAlchemy ORM models
  schemas/             # Pydantic request/response schemas
  services/            # Business logic layer
  db/
    session.py         # Database engine and session
    base.py            # Declarative base
alembic/               # Database migrations
scripts/               # Seed scripts and utilities
```

## API Documentation

When the server is running, interactive API docs are available at:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Related

- [yamacrawbusinessportal-frontend](https://github.com/yamacrawbusinessportal/yamacrawbusinessportal-frontend) - Frontend application

## License

Private. All rights reserved.
