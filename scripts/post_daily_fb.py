#!/usr/bin/env python3
"""
post_daily_fb.py — Main daily Facebook automation workflow orchestrator script.

Flow:
 1. Decrypt runtime secrets from secrets.enc using PRIMARY & FALLBACK keys.
 2. Fetch random/trending product from Shopify store.
 3. Generate high-converting Facebook feed post image (1080x1080).
 4. Generate vertical 9:16 video Reel (1080x1920).
 5. Compose engaging viral social copy + link + hashtags.
 6. Publish Post & Reel automatically to Facebook Page via Graph API.
"""

import os
import sys
import random
import logging
import argparse
from pathlib import Path

# Add script folder to path so imports work smoothly
sys.path.insert(0, str(Path(__file__).resolve().parent))

from secrets_manager import inject_to_env, get_secret
from shopify_fetcher import select_random_product
from image_generator import generate_post_image
from video_generator import generate_reel_video
from fb_publisher import publish_feed_photo, publish_facebook_reel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("post_daily_fb")


def run_daily_automation(dry_run: bool = False):
    logger.info("Initializing meeeshop-FB Daily Automation Workflow...")
    
    # 1. Inject decrypted secrets into runtime environment
    inject_to_env()
    
    brand_name = get_secret("BRAND_NAME", default="OUR STORE")
    hashtags = get_secret("POST_HASHTAGS", default="#Shopify #Deals #Shopping #Trending #Reels")
    promo_footer = get_secret("POST_FOOTER_TEXT", default="✨ Tap the link above to order yours today! FREE SHIPPING on all orders.")
    
    # 2. Fetch product catalog item
    logger.info("Fetching product catalog from Shopify store...")
    product = select_random_product()
    
    title = product["title"]
    price = product["price"]
    product_link = product["product_link"]
    
    logger.info("Selected product for today's post: '%s' ($%s)", title, price)
    
    # Randomly select 1 of 6 template style indexes for this run
    selected_style_index = random.randint(0, 5)
    logger.info("Randomly selected Template Style Index: %d of 6 available styles.", selected_style_index)

    # 3. Build social media caption
    caption = (
        f"✨ {title} ✨\n\n"
        f"🔥 Special Offer: ONLY ${price}\n"
        f"{promo_footer}\n\n"
        f"👇 SHOP NOW:\n{product_link}\n\n"
        f"{hashtags} #{brand_name.replace(' ', '')}"
    )
    
    # 4. Generate Media with Rotated Template Style
    logger.info("Generating post graphic and video Reel using Template Style %d...", selected_style_index)
    post_img_path = generate_post_image(product, "output/generated_post.png", style_index=selected_style_index)
    reel_vid_path = generate_reel_video(product, "output/generated_reel.mp4", theme_index=selected_style_index)
    
    if dry_run:
        logger.info("[DRY RUN] Media successfully generated under output/ directory. Skipping Facebook publishing.")
        logger.info("--- GENERATED CAPTION ---\n%s\n-------------------------", caption)
        return

    # 5. Publish to Facebook Page Feed & Reels
    logger.info("Publishing generated content to Facebook...")
    
    errors = []
    try:
        feed_res = publish_feed_photo(post_img_path, caption)
        logger.info("Feed Post Result: %s", feed_res)
    except Exception as e:
        logger.error("Error publishing Feed Post: %s", str(e))
        errors.append(f"Feed Post: {e}")

    try:
        reel_res = publish_facebook_reel(reel_vid_path, caption)
        logger.info("Reel Result: %s", reel_res)
    except Exception as e:
        logger.error("Error publishing Facebook Reel: %s", str(e))
        errors.append(f"Facebook Reel: {e}")

    if errors:
        logger.error("❌ meeeshop-FB Daily Automation Failed! %d publishing job(s) failed:\n - %s", len(errors), "\n - ".join(errors))
        sys.exit(1)

    logger.info("🎉 meeeshop-FB Daily Automation Completed Successfully!")


def main():
    parser = argparse.ArgumentParser(description="Automated Daily Facebook Post & Reel Publisher")
    parser.add_argument("--dry-run", action="store_true", help="Generate post & reel media without publishing to Facebook.")
    args = parser.parse_args()

    run_daily_automation(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
