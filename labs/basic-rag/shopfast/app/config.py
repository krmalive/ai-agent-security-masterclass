import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    jwt_secret: str = os.getenv("SHOPFAST_JWT_SECRET", "local-development-secret")
    jwt_issuer: str = "shopfast-api"
    access_token_minutes: int = 30
    refresh_token_days: int = 14
    payment_api: str = os.getenv("PAYMENT_API", "https://sandbox-payments.shopfast.test")
    payment_webhook_secret: str = os.getenv("PAYMENT_WEBHOOK_SECRET", "sandbox-webhook-secret")
    email_api: str = os.getenv("EMAIL_API", "https://sandbox-mail.shopfast.test")
    media_root: str = os.getenv("MEDIA_ROOT", "/var/lib/shopfast/review-media")
    allowed_origins: tuple[str, ...] = ("https://shopfast.test",)


settings = Settings()
