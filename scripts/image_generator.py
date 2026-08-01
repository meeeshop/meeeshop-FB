#!/usr/bin/env python3
"""
image_generator.py — Dynamic 6-Style Template Engine for Facebook Feed Post Graphics.

Contains 6 distinct visual template styles that rotate dynamically on each run:
 1. Style 1: `luxury_dark` (Dark Slate Gradient, Ambient Lighting & Glassmorphism)
 2. Style 2: `editorial_minimal` (Warm Clean Studio Ivory & Serif Typography)
 3. Style 3: `neon_cyber_flash` (High-Energy Midnight Purple & Electric Neon Accents)
 4. Style 4: `pastel_chic` (Soft Blush & Champagne Rose Gold Aesthetic)
 5. Style 5: `bold_retail_deal` (High-Visibility Retail & Giant Price Tag)
 6. Style 6: `magazine_showcase` (Obsidian Gold Vogue Spotlight Frame)
"""

import os
import random
import logging
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from secrets_manager import get_secret

logger = logging.getLogger(__name__)


def create_gradient(width: int, height: int, color1: tuple, color2: tuple) -> Image.Image:
    """Generate a smooth vertical gradient background."""
    base = Image.new("RGBA", (width, height), color1)
    top = Image.new("RGBA", (width, height), color2)
    mask = Image.new("L", (width, height))
    mask_draw = ImageDraw.Draw(mask)
    for y in range(height):
        alpha = int(255 * (y / height))
        mask_draw.line([(0, y), (width, y)], fill=alpha)
    base.paste(top, (0, 0), mask)
    return base


def get_fonts():
    """Load standard fonts with fallback."""
    try:
        font_brand = ImageFont.truetype("arialbd.ttf", 52)
        font_title = ImageFont.truetype("arialbd.ttf", 48)
        font_price = ImageFont.truetype("arialbd.ttf", 64)
        font_small = ImageFont.truetype("arial.ttf", 34)
        font_badge = ImageFont.truetype("arialbd.ttf", 38)
        font_cta = ImageFont.truetype("arialbd.ttf", 50)
    except IOError:
        font_brand = ImageFont.load_default()
        font_title = ImageFont.load_default()
        font_price = ImageFont.load_default()
        font_small = ImageFont.load_default()
        font_badge = ImageFont.load_default()
        font_cta = ImageFont.load_default()
    return font_brand, font_title, font_price, font_small, font_badge, font_cta


# ── STYLE 1: LUXURY DARK ───────────────────────────────────────────────────────
def render_style_1_luxury_dark(raw_img: Image.Image, product: dict, brand_name: str, public_domain: str) -> Image.Image:
    canvas = create_gradient(1080, 1080, (15, 17, 26, 255), (26, 30, 46, 255))
    glow = Image.new("RGBA", (1080, 1080), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse([50, -100, 550, 400], fill=(0, 122, 255, 35))
    glow_draw.ellipse([600, 700, 1050, 1150], fill=(255, 149, 0, 25))
    glow = glow.filter(ImageFilter.GaussianBlur(80))
    canvas.paste(glow, (0, 0), glow)

    card_w, card_h = 860, 720
    card_x, card_y = 110, 150
    shadow = Image.new("RGBA", (1080, 1080), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle([card_x + 10, card_y + 15, card_x + card_w + 10, card_y + card_h + 15], radius=35, fill=(0, 0, 0, 90))
    canvas.paste(shadow.filter(ImageFilter.GaussianBlur(25)), (0, 0), shadow)

    card_frame = Image.new("RGBA", (card_w, card_h), (255, 255, 255, 255))
    raw_img.thumbnail((780, 640), Image.Resampling.LANCZOS)
    iw, ih = raw_img.size
    card_frame.paste(raw_img, ((card_w - iw) // 2, (card_h - ih) // 2), raw_img)
    canvas.paste(card_frame, (card_x, card_y))

    draw = ImageDraw.Draw(canvas)
    f_brand, f_title, f_price, f_small, f_badge, f_cta = get_fonts()

    draw.rounded_rectangle([60, 45, 420, 110], radius=20, fill="#007AFF")
    draw.text((85, 63), f"✨ {brand_name}", fill="white", font=f_brand)
    draw.rounded_rectangle([660, 45, 1020, 110], radius=20, fill="#FF3B30")
    draw.text((680, 65), "🔥 OOTD | SHOP THE LOOK", fill="white", font=f_badge)

    price = f"${product.get('price', '0.00')}"
    draw.rounded_rectangle([130, 800, 440, 855], radius=15, fill=(18, 22, 36, 230))
    draw.text((150, 815), "5.0 ⭐⭐⭐⭐⭐ (490+ Reviews)", fill="#FFD700", font=f_small)

    draw.rounded_rectangle([650, 785, 950, 855], radius=20, fill="#28A745")
    draw.text((700, 800), f"ONLY {price}", fill="white", font=f_price)

    display_title = product.get("title", "")
    if len(display_title) > 42: display_title = display_title[:40] + "..."
    draw.rounded_rectangle([40, 875, 1040, 945], radius=15, fill=(0, 0, 0, 180))
    draw.text((60, 890), display_title, fill="white", font=f_title)

    draw.rounded_rectangle([60, 955, 1020, 1045], radius=25, fill="#007AFF")
    draw.text((160, 982), f"🛒 SHOP NOW AT  {public_domain.upper()} ➔", fill="white", font=f_cta)
    return canvas.convert("RGB")


# ── STYLE 2: EDITORIAL MINIMAL (Warm Ivory Studio) ────────────────────────────
def render_style_2_editorial_minimal(raw_img: Image.Image, product: dict, brand_name: str, public_domain: str) -> Image.Image:
    canvas = Image.new("RGBA", (1080, 1080), (248, 246, 240, 255))
    draw = ImageDraw.Draw(canvas)

    card_w, card_h = 880, 700
    card_x, card_y = 100, 160
    draw.rounded_rectangle([card_x, card_y, card_x + card_w, card_y + card_h], radius=20, fill="#FFFFFF", outline="#222222", width=3)

    raw_img.thumbnail((800, 620), Image.Resampling.LANCZOS)
    iw, ih = raw_img.size
    canvas.paste(raw_img, (card_x + (card_w - iw) // 2, card_y + (card_h - ih) // 2), raw_img)

    f_brand, f_title, f_price, f_small, f_badge, f_cta = get_fonts()

    draw.text((60, 55), brand_name, fill="#111111", font=f_brand)
    draw.rounded_rectangle([720, 50, 1020, 110], radius=10, fill="#111111")
    draw.text((745, 68), "✨ NEW DROP", fill="white", font=f_small)

    price = f"${product.get('price', '0.00')}"
    draw.rounded_rectangle([700, 780, 950, 845], radius=10, fill="#111111")
    draw.text((730, 795), price, fill="#FFFFFF", font=f_price)

    display_title = product.get("title", "")
    if len(display_title) > 40: display_title = display_title[:38] + "..."
    draw.rounded_rectangle([40, 875, 1040, 945], radius=15, fill=(255, 255, 255, 220))
    draw.text((60, 890), display_title, fill="#111111", font=f_title)

    draw.rounded_rectangle([60, 955, 1020, 1045], radius=15, fill="#111111")
    draw.text((200, 982), f"VISIT {public_domain.upper()}  |  FREE SHIPPING", fill="#FFFFFF", font=f_cta)
    return canvas.convert("RGB")


# ── STYLE 3: NEON CYBER FLASH (Midnight Purple & Electric Cyan) ───────────────
def render_style_3_neon_cyber_flash(raw_img: Image.Image, product: dict, brand_name: str, public_domain: str) -> Image.Image:
    canvas = create_gradient(1080, 1080, (18, 8, 38, 255), (42, 18, 77, 255))
    draw = ImageDraw.Draw(canvas)

    card_w, card_h = 860, 710
    card_x, card_y = 110, 150
    draw.rounded_rectangle([card_x, card_y, card_x + card_w, card_y + card_h], radius=30, fill="#FFFFFF", outline="#00F0FF", width=5)

    raw_img.thumbnail((780, 630), Image.Resampling.LANCZOS)
    iw, ih = raw_img.size
    canvas.paste(raw_img, (card_x + (card_w - iw) // 2, card_y + (card_h - ih) // 2), raw_img)

    f_brand, f_title, f_price, f_small, f_badge, f_cta = get_fonts()

    draw.rounded_rectangle([60, 45, 420, 110], radius=20, fill="#FF007A")
    draw.text((85, 63), f"⚡ {brand_name}", fill="white", font=f_brand)

    draw.rounded_rectangle([640, 45, 1020, 110], radius=20, fill="#00F0FF")
    draw.text((665, 65), "⚡ TRENDING | GET IT NOW", fill="#120826", font=f_badge)

    price = f"${product.get('price', '0.00')}"
    draw.rounded_rectangle([650, 780, 950, 850], radius=20, fill="#FF007A")
    draw.text((680, 795), price, fill="#FFFFFF", font=f_price)

    display_title = product.get("title", "")
    if len(display_title) > 42: display_title = display_title[:40] + "..."
    draw.rounded_rectangle([40, 875, 1040, 945], radius=15, fill=(18, 8, 38, 200))
    draw.text((60, 890), display_title, fill="#00F0FF", font=f_title)

    draw.rounded_rectangle([60, 955, 1020, 1045], radius=25, fill="#00F0FF")
    draw.text((150, 982), f"⚡ SHOP NOW: {public_domain.upper()} ➔", fill="#120826", font=f_cta)
    return canvas.convert("RGB")


# ── STYLE 4: PASTEL CHIC (Blush & Champagne Rose Gold) ───────────────────────
def render_style_4_pastel_chic(raw_img: Image.Image, product: dict, brand_name: str, public_domain: str) -> Image.Image:
    canvas = create_gradient(1080, 1080, (253, 240, 240, 255), (250, 243, 224, 255))
    draw = ImageDraw.Draw(canvas)

    card_w, card_h = 860, 710
    card_x, card_y = 110, 150
    draw.rounded_rectangle([card_x, card_y, card_x + card_w, card_y + card_h], radius=35, fill="#FFFFFF", outline="#E8B4B8", width=4)

    raw_img.thumbnail((780, 630), Image.Resampling.LANCZOS)
    iw, ih = raw_img.size
    canvas.paste(raw_img, (card_x + (card_w - iw) // 2, card_y + (card_h - ih) // 2), raw_img)

    f_brand, f_title, f_price, f_small, f_badge, f_cta = get_fonts()

    draw.rounded_rectangle([60, 45, 420, 110], radius=20, fill="#D87093")
    draw.text((85, 63), f"🌸 {brand_name}", fill="white", font=f_brand)

    draw.rounded_rectangle([660, 45, 1020, 110], radius=20, fill="#C71585")
    draw.text((680, 65), "💖 ROMANTIC ERA", fill="white", font=f_badge)

    price = f"${product.get('price', '0.00')}"
    draw.rounded_rectangle([650, 780, 950, 850], radius=20, fill="#D87093")
    draw.text((690, 795), price, fill="#FFFFFF", font=f_price)

    display_title = product.get("title", "")
    if len(display_title) > 42: display_title = display_title[:40] + "..."
    draw.rounded_rectangle([40, 875, 1040, 945], radius=15, fill=(255, 255, 255, 200))
    draw.text((60, 890), display_title, fill="#8B008B", font=f_title)

    draw.rounded_rectangle([60, 955, 1020, 1045], radius=25, fill="#D87093")
    draw.text((180, 982), f"🌸 SHOP NOW AT {public_domain.upper()}", fill="white", font=f_cta)
    return canvas.convert("RGB")


# ── STYLE 5: BOLD RETAIL DEAL (High-Visibility Retail & Yellow Accent) ───────
def render_style_5_bold_retail_deal(raw_img: Image.Image, product: dict, brand_name: str, public_domain: str) -> Image.Image:
    canvas = Image.new("RGBA", (1080, 1080), (30, 34, 42, 255))
    draw = ImageDraw.Draw(canvas)

    card_w, card_h = 880, 700
    card_x, card_y = 100, 160
    draw.rounded_rectangle([card_x, card_y, card_x + card_w, card_y + card_h], radius=25, fill="#FFFFFF")

    raw_img.thumbnail((800, 620), Image.Resampling.LANCZOS)
    iw, ih = raw_img.size
    canvas.paste(raw_img, (card_x + (card_w - iw) // 2, card_y + (card_h - ih) // 2), raw_img)

    f_brand, f_title, f_price, f_small, f_badge, f_cta = get_fonts()

    draw.rounded_rectangle([60, 45, 450, 110], radius=15, fill="#FFCC00")
    draw.text((85, 63), f"🔥 {brand_name} DEALS", fill="#000000", font=f_brand)

    draw.rounded_rectangle([640, 45, 1020, 110], radius=15, fill="#E63946")
    draw.text((670, 65), "💰 FASHION STEAL", fill="white", font=f_badge)

    price = f"${product.get('price', '0.00')}"
    draw.rounded_rectangle([650, 780, 950, 850], radius=15, fill="#FFCC00")
    draw.text((680, 795), f"PRICE: {price}", fill="#000000", font=f_price)

    display_title = product.get("title", "")
    if len(display_title) > 42: display_title = display_title[:40] + "..."
    draw.rounded_rectangle([40, 875, 1040, 945], radius=15, fill=(0, 0, 0, 180))
    draw.text((60, 890), display_title, fill="white", font=f_title)

    draw.rounded_rectangle([60, 955, 1020, 1045], radius=20, fill="#FFCC00")
    draw.text((160, 982), f"🛒 BUY NOW: {public_domain.upper()} ➔", fill="#000000", font=f_cta)
    return canvas.convert("RGB")


# ── STYLE 6: MAGAZINE SHOWCASE (Obsidian Gold Vogue Spotlight) ──────────────
def render_style_6_magazine_showcase(raw_img: Image.Image, product: dict, brand_name: str, public_domain: str) -> Image.Image:
    canvas = Image.new("RGBA", (1080, 1080), (9, 9, 11, 255))
    draw = ImageDraw.Draw(canvas)

    # Double Gold Border Frame
    draw.rectangle([30, 30, 1050, 1050], outline="#D4AF37", width=3)
    draw.rectangle([40, 40, 1040, 1040], outline="#D4AF37", width=1)

    card_w, card_h = 860, 700
    card_x, card_y = 110, 160
    draw.rounded_rectangle([card_x, card_y, card_x + card_w, card_y + card_h], radius=20, fill="#FFFFFF")

    raw_img.thumbnail((780, 620), Image.Resampling.LANCZOS)
    iw, ih = raw_img.size
    canvas.paste(raw_img, (card_x + (card_w - iw) // 2, card_y + (card_h - ih) // 2), raw_img)

    f_brand, f_title, f_price, f_small, f_badge, f_cta = get_fonts()

    draw.text((70, 70), f"♦ STYLE TIPS | {brand_name} ♦", fill="#D4AF37", font=f_brand)

    price = f"${product.get('price', '0.00')}"
    draw.rounded_rectangle([660, 780, 950, 845], radius=10, fill="#D4AF37")
    draw.text((690, 795), price, fill="#000000", font=f_price)

    display_title = product.get("title", "")
    if len(display_title) > 42: display_title = display_title[:40] + "..."
    draw.rounded_rectangle([50, 875, 1030, 945], radius=15, fill=(0, 0, 0, 200))
    draw.text((70, 890), display_title, fill="#FFFFFF", font=f_title)

    draw.rounded_rectangle([70, 955, 1010, 1030], radius=15, fill="#D4AF37")
    draw.text((200, 975), f"EXPLORE AT {public_domain.upper()} ➔", fill="#000000", font=f_cta)
    return canvas.convert("RGB")


# ── MAIN ENGINE ────────────────────────────────────────────────────────────────

STYLES = [
    ("luxury_dark", render_style_1_luxury_dark),
    ("editorial_minimal", render_style_2_editorial_minimal),
    ("neon_cyber_flash", render_style_3_neon_cyber_flash),
    ("pastel_chic", render_style_4_pastel_chic),
    ("bold_retail_deal", render_style_5_bold_retail_deal),
    ("magazine_showcase", render_style_6_magazine_showcase)
]


def generate_post_image(product: dict, output_path: str = "output/generated_post.png", style_index: int = None) -> str:
    """Generate a 1080x1080 feed post graphic using one of 6 dynamic template styles."""
    brand_name = get_secret("BRAND_NAME", default="MEEESHOP").upper()
    public_domain = get_secret("PUBLIC_STORE_DOMAIN", default="us.meeeshop.com")

    img_urls = product.get("images", [])
    if not img_urls:
        raise ValueError("Product contains no image URLs.")

    response = requests.get(img_urls[0], timeout=15)
    response.raise_for_status()
    raw_img = Image.open(BytesIO(response.content)).convert("RGBA")

    # Select template style (random or specified index)
    if style_index is None or not (0 <= style_index < len(STYLES)):
        style_name, render_fn = random.choice(STYLES)
    else:
        style_name, render_fn = STYLES[style_index]

    logger.info("Selected Image Post Template Style: '%s'", style_name)

    final_img = render_fn(raw_img, product, brand_name, public_domain)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    final_img.save(output_path, "PNG", quality=98)
    return output_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Multi-template image generator ready.")
