import {api} from "./api.js";
import {activeBasket} from "./basket.js";

function idempotencyKey() {
  return window.crypto.randomUUID();
}

export async function placeOrder({addressId, paymentToken, giftCardCode = null}) {
  const basket = await activeBasket();
  return api(`/baskets/${basket.id}/checkout`, {
    method: "POST",
    headers: {"Idempotency-Key": idempotencyKey()},
    body: JSON.stringify({
      address_id: addressId,
      payment_token: paymentToken,
      gift_card_code: giftCardCode,
    }),
  });
}

export async function orderHistory() {
  return api("/orders");
}

export async function cancelOrder(orderId) {
  return api(`/orders/${orderId}/cancel`, {method: "POST"});
}
