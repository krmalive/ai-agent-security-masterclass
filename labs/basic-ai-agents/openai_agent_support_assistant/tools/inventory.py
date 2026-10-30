"""Inventory lookup tool for product availability and details"""

from agents import function_tool


INVENTORY_DB = {
    "laptop": {
        "name": "UltraBook Pro 15",
        "stock": 12,
        "price": 1299.99,
        "category": "Electronics",
        "description": "15-inch laptop with 16GB RAM, 512GB SSD"
    },
    "phone": {
        "name": "SmartPhone X",
        "stock": 45,
        "price": 899.99,
        "category": "Electronics",
        "description": "Latest smartphone with 5G, 128GB storage"
    },
    "headphones": {
        "name": "NoiseCancelling Pro",
        "stock": 0,
        "price": 299.99,
        "category": "Audio",
        "description": "Premium wireless headphones with active noise cancellation"
    },
    "keyboard": {
        "name": "Mechanical RGB Keyboard",
        "stock": 28,
        "price": 149.99,
        "category": "Accessories",
        "description": "RGB mechanical keyboard with blue switches"
    },
    "mouse": {
        "name": "Wireless Gaming Mouse",
        "stock": 35,
        "price": 79.99,
        "category": "Accessories",
        "description": "Ergonomic wireless mouse with programmable buttons"
    },
    "monitor": {
        "name": "UltraWide 34-inch Monitor",
        "stock": 8,
        "price": 599.99,
        "category": "Electronics",
        "description": "34-inch curved monitor, 3440x1440 resolution"
    },
    "tablet": {
        "name": "ProTab 12",
        "stock": 15,
        "price": 799.99,
        "category": "Electronics",
        "description": "12-inch tablet with stylus support"
    },
    "charger": {
        "name": "Fast Charger 65W",
        "stock": 50,
        "price": 39.99,
        "category": "Accessories",
        "description": "Universal USB-C fast charger"
    }
}


@function_tool
def lookup_inventory(product: str) -> str:
    """
    Look up product availability and details in inventory.
    
    Args:
        product: The product name or type to search for (e.g., 'laptop', 'phone', 'headphones')
        
    Returns:
        A formatted string with product details and availability
    """
    product_key = product.lower().strip()
    
    if product_key in INVENTORY_DB:
        item = INVENTORY_DB[product_key]
        availability = "In Stock" if item["stock"] > 0 else "Out of Stock"
        return (
            f"Product: {item['name']}\n"
            f"Category: {item['category']}\n"
            f"Price: ${item['price']}\n"
            f"Stock: {item['stock']} units ({availability})\n"
            f"Description: {item['description']}"
        )

    matches = []
    for key, item in INVENTORY_DB.items():
        if product_key in key or product_key in item['name'].lower():
            matches.append((key, item))
    
    if matches:
        results = []
        for key, item in matches:
            availability = "In Stock" if item["stock"] > 0 else "Out of Stock"
            results.append(
                f"• {item['name']} ({availability}): ${item['price']} - {item['stock']} units available"
            )
        return "Found matching products:\n" + "\n".join(results)
    
    return f"Product '{product}' not found in inventory. Available products: {', '.join(INVENTORY_DB.keys())}"

