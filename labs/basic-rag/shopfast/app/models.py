from typing import Literal

from pydantic import BaseModel, Field

Email = str


class Registration(BaseModel):
    email: Email = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=254)
    password: str = Field(min_length=10, max_length=128)
    display_name: str = Field(min_length=2, max_length=80)


class Login(BaseModel):
    email: Email = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=254)
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class PasswordResetRequest(BaseModel):
    email: Email = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=254)


class PasswordReset(BaseModel):
    token: str
    new_password: str = Field(min_length=10, max_length=128)


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=80)
    phone: str | None = Field(default=None, max_length=30)


class AddressInput(BaseModel):
    label: str = Field(max_length=40)
    recipient: str = Field(max_length=100)
    line1: str = Field(max_length=150)
    line2: str | None = Field(default=None, max_length=150)
    city: str = Field(max_length=80)
    postal_code: str = Field(max_length=20)
    country: str = Field(min_length=2, max_length=2)


class BasketItemInput(BaseModel):
    product_id: int
    quantity: int = Field(ge=1, le=20)


class CouponInput(BaseModel):
    code: str = Field(min_length=3, max_length=40)


class CheckoutRequest(BaseModel):
    address_id: int
    payment_token: str
    gift_card_code: str | None = None


class ReviewInput(BaseModel):
    product_id: int
    rating: int = Field(ge=1, le=5)
    body_markdown: str = Field(min_length=3, max_length=5000)


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=150)
    price_cents: int | None = Field(default=None, ge=0)
    inventory: int | None = Field(default=None, ge=0)
    status: Literal["draft", "active", "archived"] | None = None


class RefundInput(BaseModel):
    amount_cents: int = Field(gt=0)
    reason: str = Field(min_length=5, max_length=300)
