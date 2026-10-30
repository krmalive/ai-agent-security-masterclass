import {addProduct} from "./basket.js";
import {loadCatalog, renderProducts} from "./catalog.js";

const catalog = document.querySelector("#catalog");
const search = document.querySelector("#search");
const sort = document.querySelector("#sort");
const status = document.querySelector("#status");

async function refreshCatalog() {
  try {
    const result = await loadCatalog({query: search.value, sort: sort.value});
    renderProducts(catalog, result.items, async (productId) => {
      await addProduct(productId);
      status.textContent = "Product added to your basket";
    });
  } catch (error) {
    status.textContent = error.message;
  }
}

search.addEventListener("input", refreshCatalog);
sort.addEventListener("change", refreshCatalog);
refreshCatalog();
