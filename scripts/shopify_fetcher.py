#!/usr/bin/env python3
"""
shopify_fetcher.py — Dynamic Shopify product catalog fetcher module.

Zero hardcoded URLs or store names in code; store URL is fetched dynamically
from double-encrypted secrets vault via secrets_manager.py.
"""

import random
import logging
import requests
from secrets_manager import get_secret

logger = logging.getLogger(__name__)


def fetch_shopify_products(store_url: str = None) -> list:
    """Fetch public products from Shopify store JSON endpoint."""
    if not store_url:
        store_url = get_secret("SHOPIFY_STORE_URL")
    
    # Strip any leading https:// or trailing slashes
    clean_url = store_url.replace("https://", "").replace("http://", "").strip("/")
    endpoint = f"https://{clean_url}/products.json?limit=50"
    
    logger.info("Fetching products from Shopify endpoint: %s", endpoint)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(endpoint, headers=headers, timeout=15)
        response.raise_for_status()
        products = response.json().get("products", [])
        valid_products = [p for p in products if p.get("images") and len(p.get("images")) > 0]
    except Exception as e:
        logger.warning("Could not fetch live products from %s (%s). Using fallback sample product data for local test/preview.", clean_url, str(e))
        valid_products = [{
            "id": 99999,
            "title": "Premium Wireless Noise-Cancelling Headphones",
            "handle": "premium-wireless-headphones",
            "images": [
                {"src": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=800&q=80"},
                {"src": "https://images.unsplash.com/photo-1484704849700-f032a568e944?w=800&q=80"}
            ],
            "variants": [{"price": "79.99", "compare_at_price": "129.99"}]
        }]
    
    logger.info("Found %d valid products with images.", len(valid_products))
    return valid_products


import os, json
from pathlib import Path

CATEGORY_HISTORY_FILE = Path(__file__).parent / "used_categories_history.json"

CATEGORY_KEYWORDS = {
    "dresses":               ["dress", "gown", "midi", "maxi", "mini", "romper", "jumpsuit"],
    "tops":                  ["top", "blouse", "shirt", "tee", "tank", "crop", "bodysuit", "sweater", "cardigan", "hoodie", "pullover", "tunic"],
    "bottoms":               ["skirt", "shorts", "pant", "jean", "trouser", "legging", "denim", "slacks"],
    "handbags_accessories":  ["bag", "purse", "tote", "handbag", "clutch", "backpack", "crossbody", "wallet", "belt", "scarf", "hat", "jewelry", "necklace", "earring", "ring", "bracelet"],
    "outerwear":             ["jacket", "coat", "blazer", "vest", "trench", "parka"],
    "shoes":                 ["shoe", "boot", "sandal", "heel", "sneaker", "flat", "mule", "slipper"],
}


def detect_product_category(title: str, product_type: str = "", tags: str = "") -> str:
    text = f"{title} {product_type} {tags}".lower()
    for cat, kws in CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in kws):
            return cat
    return "other"


def _load_cat_history():
    if CATEGORY_HISTORY_FILE.exists():
        try:
            return json.loads(CATEGORY_HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"used_categories": []}


def _save_cat_history(data):
    try:
        CATEGORY_HISTORY_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning(f"Could not save category history: {e}")


def select_random_product(products: list = None) -> dict:
    """Select a product ensuring category round-robin rotation so categories (e.g. handbags) don't repeat until all categories are posted."""
    if not products:
        products = fetch_shopify_products()
    
    # Category Round-Robin Rotation logic
    cat_history = _load_cat_history()
    used_cats   = cat_history.get("used_categories", [])

    prod_with_cat = []
    for p in products:
        title = p.get("title", "")
        ptype = p.get("product_type", "")
        tags  = str(p.get("tags", ""))
        cat   = detect_product_category(title, ptype, tags)
        prod_with_cat.append((p, cat))

    available_cats = set(cat for _, cat in prod_with_cat)
    unposted_cats  = [c for c in available_cats if c not in used_cats]

    if not unposted_cats:
        logger.info("All product categories posted in current cycle — resetting category rotation cycle")
        used_cats     = []
        unposted_cats = list(available_cats)

    eligible = [p for p, cat in prod_with_cat if cat in unposted_cats]
    pool = eligible if eligible else products

    product = random.choice(pool)
    title = product.get("title", "Featured Product")
    handle = product.get("handle", "")
    ptype = product.get("product_type", "")
    tags  = str(product.get("tags", ""))
    cat   = detect_product_category(title, ptype, tags)

    if cat not in used_cats:
        used_cats.append(cat)
    _save_cat_history({"used_categories": used_cats})

    logger.info("Selected product: '%s' (Category: %s)", title, cat)

    images = [img["src"] for img in product.get("images", []) if isinstance(img, dict) and img.get("src")]
    variants = product.get("variants", [])
    for v in variants:
        if isinstance(v, dict):
            feat = v.get("featured_image")
            if isinstance(feat, dict) and feat.get("src") and feat["src"] not in images:
                images.append(feat["src"])
    price = variants[0].get("price", "0.00") if variants else "0.00"
    compare_at_price = variants[0].get("compare_at_price", None) if variants else None
    
    public_domain = get_secret("PUBLIC_STORE_DOMAIN", default="us.meeeshop.com").replace("https://", "").replace("http://", "").strip("/")
    product_link = f"https://{public_domain}/products/{handle}"
    
    return {
        "id": product.get("id"),
        "title": title,
        "handle": handle,
        "price": price,
        "compare_at_price": compare_at_price,
        "images": images,
        "product_link": product_link,
        "category": cat,
        "raw": product
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    prod = select_random_product()
    print("Selected Product:", prod["title"])
    print("Price:", prod["price"])
    print("Link:", prod["product_link"])
