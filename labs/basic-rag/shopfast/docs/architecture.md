# ShopFast architecture and workflows

## Trust boundaries

1. The browser stores an access token and refresh token, then sends the access token as a bearer credential.
2. Public catalog endpoints cross from the internet into catalog search and filtering.
3. Authenticated customer endpoints access profiles, addresses, baskets, reviews, and orders.
4. Administrator endpoints use the same JWT issuer but require an `admin` role claim.
5. Checkout sends payment tokens, amounts, and order references to a third-party provider.
6. The payment provider calls a public webhook that updates order payment status.
7. Password reset and order events send messages through an email provider.
8. Review images are accepted as multipart uploads and later served by a media tier.

## Important workflows

### Account recovery

`POST /api/auth/password-reset/request` creates a single-use reset token and sends an email. `POST /api/auth/password-reset/confirm` consumes it. Responses to the request endpoint are intentionally uniform for known and unknown accounts.

### Basket and checkout

A signed-in user creates a basket, adds products, applies a coupon, and supplies a saved or inline shipping address. Checkout accepts an `Idempotency-Key`, calculates totals server-side, creates a pending order, and authorizes payment. Gift cards may reduce the remaining payment amount.

### Payment completion

The provider posts `payment.authorized`, `payment.failed`, or `refund.completed` events to `/api/webhooks/payments`. The handler verifies a shared-secret signature and records provider event IDs before changing an order.

### Reviews

Customers create Markdown reviews and may upload JPEG or PNG attachments. Review ownership is checked for edits and administrators can moderate any review.

## Object ownership

- Users own addresses, baskets, orders, gift cards assigned to their account, and reviews.
- Basket, order, product, review, and address resources use numeric identifiers.
- Administrators may list customers and orders, update inventory, moderate reviews, issue refunds, and export reports.
