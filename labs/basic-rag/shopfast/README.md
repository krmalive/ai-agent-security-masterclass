# ShopFast storefront

ShopFast is a compact but realistic FastAPI commerce application used as the code input for the Agentic RAG lab. It is large enough to contain meaningful trust boundaries and multi-step workflows while remaining readable during a lab.

## Product capabilities

- Customer registration, login, refresh tokens, profile management, and email password reset
- Public product catalog with search, sorting, category filters, and product detail pages
- Customer baskets addressed by numeric IDs, coupon application, and basket sharing
- Checkout with gift cards, coupons, shipping addresses, idempotency keys, and a payment provider
- Customer order history, order detail, cancellation, and administrator refunds
- Product reviews with Markdown comments and image attachments
- Administrator product, order, customer, and CSV export operations
- Signed payment-provider webhooks for asynchronous payment state changes
- Browser modules for catalog, baskets, checkout, and local-storage sessions

## Runtime architecture

```text
Browser SPA
   │ JWT access + refresh tokens
   ▼
FastAPI routes ──► domain services ──► repository/store
   │                    │
   │                    ├──► email notification provider
   │                    └──► payment provider
   ▼
Payment webhook endpoint
```

The repository is in-memory so the fixture stays self-contained, but routes and services follow the same boundaries as a database-backed application. See [docs/architecture.md](docs/architecture.md) for workflows and ownership rules.

## Engagement context

- Three tester-days
- Black-box execution; the agent sees source only while constructing the plan
- Production-safe testing only
- Test accounts and sandbox payment tokens are available
- No denial of service, destructive bulk actions, real charges, or access to real customer data

The fixture is planning input. It is not an intentionally exploitable target and should not be attacked.
