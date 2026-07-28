# meeeshop-FB — Automated Shopify Facebook Feed & Reels Marketing Publisher

`meeeshop-FB` is an automated, zero-hardcode marketing pipeline that fetches products from your Shopify store, generates high-converting **1:1 Image Posts** and **9:16 Vertical Video Reels**, and publishes them automatically to your Facebook Page via the Meta Graph API.

---

## 🔒 Security Architecture (Double-Fernet Encryption)

To comply with repository and organization security standards (matching `meeeshop-seo` and `meeeshop-pinterest`):
- **Zero Hardcoded Secrets or Identifiers:** No store URLs, brand names, Page IDs, or API tokens exist in plain text within source code.
- **Encrypted Vault (`secrets.enc`):** All sensitive keys, brand details, and credentials are stored inside `secrets.enc` encrypted using **Double-Fernet Encryption**:
  $$\text{Fernet}_{\text{PRIMARY}}\left(\text{Fernet}_{\text{FALLBACK}}\left(\text{plaintext}\right)\right)$$
- **Runtime Decryption:** `scripts/secrets_manager.py` decrypts credentials dynamically in memory during execution using `ENCRYPTION_KEY_PRIMARY` and `ENCRYPTION_KEY_FALLBACK`.
- **SecretSanitizer:** All loggers automatically scrub decrypted secret values to prevent token exposure in build logs or console outputs.

---

## 📁 Repository Structure

```text
meeeshop-FB/
├── .env                              # Local encryption keys (git-ignored)
├── .env.example                      # Template for environment variables
├── .gitignore                        # Git exclusions for secrets & temp media
├── README.md                         # Project documentation
├── requirements.txt                  # Python dependencies
├── secrets.enc                       # Double-Fernet encrypted credentials vault
├── output/                           # Output directory for generated media
├── scripts/
│   ├── secrets_manager.py            # Double-Fernet decryption engine & SecretSanitizer
│   ├── encrypt_secrets.py            # CLI tool to encrypt JSON secrets into secrets.enc
│   ├── shopify_fetcher.py            # Shopify store catalog fetcher
│   ├── image_generator.py            # 1080x1080 Facebook feed post graphic generator
│   ├── video_generator.py            # 9:16 vertical video reel generator (MoviePy/FFmpeg)
│   ├── fb_publisher.py               # Meta Graph API publisher for Feed Photos & Reels
│   └── post_daily_fb.py              # Main daily automation orchestrator script
└── .github/
    └── workflows/
        └── daily_fb_automation.yml   # GitHub Actions workflow scheduled daily at 09:00 UTC
```

---

## 🚀 Quick Start (Local Development & Testing)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run Local Dry-Run Test
To test image card and video reel generation locally without posting to Facebook:
```bash
python scripts/post_daily_fb.py --dry-run
```
*Generated media will be saved under `output/generated_post.png` and `output/generated_reel.mp4`.*

---

## 🔐 Encrypting Your Secrets

To update your credentials (e.g., updating store URL or Facebook Page Token):

1. Edit your plaintext credentials JSON (e.g., `my_secrets.json`):
   ```json
   {
     "SHOPIFY_STORE_URL": "your-store.myshopify.com",
     "FB_PAGE_ID": "YOUR_PAGE_ID",
     "FB_ACCESS_TOKEN": "YOUR_PERMANENT_PAGE_TOKEN",
     "BRAND_NAME": "YOUR_BRAND",
     "STORE_NAME": "YOUR_STORE_NAME",
     "POST_HASHTAGS": "#YourBrand #Shopify #Deals #Reels",
     "POST_FOOTER_TEXT": "✨ Tap link below to order!",
     "PROMO_BADGE_TEXT": "🔥 TRENDING NOW",
     "POST_CTA_TEXT": "🛒 TAP LINK IN CAPTION TO SHOP!",
     "REEL_HEADLINE": "🔥 NEW ARRIVAL | TRENDING NOW"
   }
   ```

2. Run the encryption script:
   ```bash
   python scripts/encrypt_secrets.py --input my_secrets.json --output secrets.enc
   ```

3. Delete your unencrypted `my_secrets.json` file.

---

## ⚙️ GitHub Actions Workflow Setup

To run automated daily posting on GitHub Actions:

1. Push this repository to GitHub.
2. Go to **Repository Settings** $\rightarrow$ **Secrets and variables** $\rightarrow$ **Actions**.
3. Add the following **Repository Secrets**:
   * `ENCRYPTION_KEY_PRIMARY`: *(Value from your `.env` file)*
   * `ENCRYPTION_KEY_FALLBACK`: *(Value from your `.env` file)*
4. The workflow in `.github/workflows/daily_fb_automation.yml` will automatically trigger daily at **09:00 AM UTC** or can be manually triggered via **Actions $\rightarrow$ Run workflow**.
