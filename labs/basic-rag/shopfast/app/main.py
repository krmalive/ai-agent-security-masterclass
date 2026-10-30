from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .middleware import RequestContextMiddleware
from .routes import accounts, admin, auth, baskets, catalog, orders, reviews, webhooks

app = FastAPI(title="ShopFast API", version="2.3")
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["authentication"])
app.include_router(accounts.router, prefix="/api/account", tags=["account"])
app.include_router(catalog.router, prefix="/api/catalog", tags=["catalog"])
app.include_router(baskets.router, prefix="/api/baskets", tags=["baskets"])
app.include_router(orders.router, prefix="/api/orders", tags=["orders"])
app.include_router(reviews.router, prefix="/api/reviews", tags=["reviews"])
app.include_router(admin.router, prefix="/api/admin", tags=["administration"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["webhooks"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "shopfast-api", "version": "2.3"}
