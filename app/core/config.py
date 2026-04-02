from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Yamacraw Business Portal API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql://yamacraw:yamacraw_dev@localhost:5432/yamacraw_portal"

    # JWT
    JWT_SECRET_KEY: str = "CHANGE-ME-IN-PRODUCTION"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173"

    # Email (Resend)
    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "Yamacraw Business Portal <info@yamacrawbusinessportal.com>"
    CONTACT_EMAIL: str = "info@yamacrawbusinessportal.com"

    # Turnstile CAPTCHA
    TURNSTILE_SECRET_KEY: str = ""

    # Uploads
    UPLOAD_DIR: str = "./uploads"
    MAX_IMAGE_SIZE_MB: int = 5
    MAX_PHOTOS_PER_BUSINESS: int = 10
    MAX_LISTINGS_PER_OWNER: int = 5

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
