import {api} from "./api.js";

const ACTIVE_BASKET_KEY = "shopfast_active_basket";

export async function activeBasket() {
  let basketId = window.sessionStorage.getItem(ACTIVE_BASKET_KEY);
  if (!basketId) {
    const basket = await api("/baskets", {method: "POST"});
    basketId = String(basket.id);
    window.sessionStorage.setItem(ACTIVE_BASKET_KEY, basketId);
  }
  return api(`/baskets/${basketId}`);
}

export async function addProduct(productId, quantity = 1) {
  const basket = await activeBasket();
  return api(`/baskets/${basket.id}/items`, {
    method: "POST",
    body: JSON.stringify({product_id: productId, quantity}),
  });
}

export async function applyCoupon(code) {
  const basket = await activeBasket();
  return api(`/baskets/${basket.id}/coupon`, {
    method: "POST",
    body: JSON.stringify({code}),
  });
}

export async function shareBasket() {
  const basket = await activeBasket();
  return api(`/baskets/${basket.id}/share`, {method: "POST"});
}
