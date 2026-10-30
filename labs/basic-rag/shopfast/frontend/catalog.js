import {api} from "./api.js";

export async function loadCatalog({query = "", category = "", sort = "name", page = 1} = {}) {
  const params = new URLSearchParams({q: query, sort, page: String(page)});
  if (category) params.set("category", category);
  return api(`/catalog/products?${params}`);
}

export async function loadProduct(productId) {
  return api(`/catalog/products/${productId}`);
}

export function renderProducts(container, products, onAdd) {
  container.replaceChildren(...products.map((product) => {
    const card = document.createElement("article");
    card.className = "product-card";
    card.innerHTML = `<h3></h3><p></p><strong></strong><button type="button">Add to basket</button>`;
    card.querySelector("h3").textContent = product.name;
    card.querySelector("p").textContent = product.description;
    card.querySelector("strong").textContent = `$${(product.price_cents / 100).toFixed(2)}`;
    card.querySelector("button").addEventListener("click", () => onAdd(product.id));
    return card;
  }));
}
