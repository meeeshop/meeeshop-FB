#!/usr/bin/env python3
import os, glob, io, random, time, tempfile, textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import requests
from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageFilter
from moviepy.editor import AudioFileClip, CompositeAudioClip, VideoClip, concatenate_videoclips
import logging

logger = logging.getLogger(__name__)

from secrets_manager import get_secret

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

VIDEO_HISTORY_FILE = Path(__file__).parent / "video_posting_history.json"
VIDEO_REPOST_COOLDOWN_DAYS = 10
_AUDIO_DIR = Path(__file__).parent / "audio"

MAX_PINS_PER_RUN = int(os.getenv("MAX_PINS_PER_RUN", "3"))
DRY_RUN = os.getenv("DRY_RUN", "false").lower() in ("1", "true", "yes")
MAX_VIDEO_SIZE_MB = 100
BRAND_NAME = os.getenv("BRAND_NAME", "MeeeShop US Boutique")
GTTS_TLD = "com"  # US Accent for gTTS voiceover
GTTS_LANG = "en"

# Pinterest pin creation endpoint (web-UI flow — no OAuth app needed)
_PINTEREST_PIN_URL = "https://www.pinterest.com/resource/PinResource/create/"

# Boards preferred for video content
VIDEO_PREFERRED_BOARDS = [
    "Trends",
    "Outfit Ideas",
    "Style Ideas",
    "Everyday Style",
    "Chic & Effortless Styles",
    "New Trendy Women Apparel, Shoes, Handbags & more",
    "Simple Outfits",
    "Ootd #ootd",
]

# ---------------------------------------------------------------------------
# Video build config (mirrors youtube_shorts.py)
# ---------------------------------------------------------------------------

VIDEO_W, VIDEO_H  = 1080, 1920
FPS               = 30
CLIP_DURATION     = 1.0    # seconds per product image slide
VOICEOVER_DURATION = 4     # max voiceover length in seconds
OUT_DIR           = Path(tempfile.gettempdir())
OUT_DIR.mkdir(exist_ok=True)

FORMATS = [
    {"badge": "OOTD",          "cta": "Shop The Look",        "badge_color": (255, 200, 50)},
    {"badge": "TRENDING",      "cta": "Get It Now",            "badge_color": (255, 50, 100)},
    {"badge": "NEW DROP",      "cta": "Shop Before It's Gone", "badge_color": (50, 200, 100)},
    {"badge": "STYLE TIPS",    "cta": "See All Styles",        "badge_color": (80, 160, 255)},
    {"badge": "FASHION STEAL", "cta": "Grab This Deal",        "badge_color": (255, 130, 50)},
    {"badge": "STYLE INSPO",   "cta": "Get The Look",          "badge_color": (180, 80, 255)},
    {"badge": "MUST HAVE",     "cta": "Add To Cart",           "badge_color": (210, 160, 140)},
    {"badge": "ROMANTIC ERA",  "cta": "Elevate Your Look",     "badge_color": (115, 30, 70)},
    {"badge": "VIBE CHECK",    "cta": "Shop The Vibe",         "badge_color": (70, 95, 120)},
    {"badge": "DAILY RITUAL",  "cta": "Get The Look",          "badge_color": (60, 105, 80)},
]

SOLID_BG_COLORS = [
    (248, 240, 235),  # warm cream
    (240, 235, 248),  # soft lavender
    (235, 248, 240),  # mint green
    (248, 235, 240),  # blush pink
    (235, 245, 250),  # sky blue
    (250, 245, 235),  # peach
    (240, 240, 248),  # periwinkle
    (245, 238, 230),  # linen
]

# Font paths (CI = Linux, local = Windows)
import platform
if platform.system() == "Windows":
    _FONT_BOLD = "C:/Windows/Fonts/arialbd.ttf"
    _FONT_REG  = "C:/Windows/Fonts/arial.ttf"
else:
    _FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    _FONT_REG  = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(_FONT_BOLD if bold else _FONT_REG, size)
    except Exception:
        return ImageFont.load_default()


# ---------------------------------------------------------------------------
# History helpers
# ---------------------------------------------------------------------------

def _load_history() -> Dict[str, Any]:
    if VIDEO_HISTORY_FILE.exists():
        try:
            return json.loads(VIDEO_HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"posts": []}


def _save_history(history: Dict[str, Any]) -> None:
    VIDEO_HISTORY_FILE.write_text(
        json.dumps(history, indent=2, default=str), encoding="utf-8"
    )


def _was_recently_posted(product: Dict[str, Any], video_history: Dict[str, Any]) -> bool:
    product_handle = product.get("handle", "")
    product_id = str(product.get("id", ""))
    
    cutoff = datetime.now(timezone.utc) - timedelta(days=VIDEO_REPOST_COOLDOWN_DAYS)
    
    # 1. Check video history (by handle or ID)
    for post in video_history.get("posts", []):
        post_handle = post.get("product_handle")
        post_id = str(post.get("product_id", ""))
        if (post_handle and post_handle == product_handle) or (post_id and post_id == product_id):
            try:
                posted_at = datetime.fromisoformat(post["posted_at"])
                if posted_at.tzinfo is None:
                    posted_at = posted_at.replace(tzinfo=timezone.utc)
                if posted_at > cutoff:
                    return True
            except Exception:
                pass

    # 2. Check other history files
    history_files = [
        ("posting_history_v2.json", "posts", "timestamp"),
        ("refresh_history_v2.json", "refreshes", "timestamp"),
        ("posting_history.json", "posts", "timestamp"),
        ("refresh_history.json", "refreshes", "timestamp"),
        ("blog_posting_history.json", "posts", "timestamp"),
    ]
    
    for filename, list_key, time_key in history_files:
        path = Path(__file__).parent / filename
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                for item in data.get(list_key, []):
                    item_id = str(item.get("product_id") or item.get("id") or "")
                    item_handle = item.get("product_handle") or item.get("handle")
                    if (item_id and item_id == product_id) or (item_handle and item_handle == product_handle):
                        ts_str = item.get(time_key) or item.get("posted_at")
                        if ts_str:
                            ts = datetime.fromisoformat(ts_str)
                            if ts.tzinfo is None:
                                ts = ts.replace(tzinfo=timezone.utc)
                            if ts > cutoff:
                                return True
            except Exception as e:
                logger.warning(f"Error reading history file {filename}: {e}")
                
    return False


# ---------------------------------------------------------------------------
# Frame / video building (adapted from youtube_shorts.py)
# ---------------------------------------------------------------------------

def _solid_bg(color: tuple, w: int = VIDEO_W, h: int = VIDEO_H) -> Image.Image:
    img = Image.new("RGB", (w, h))
    dr  = ImageDraw.Draw(img)
    r0, g0, b0 = color
    for y in range(h):
        t = y / h
        dr.line([(0, y), (w, y)], fill=(int(r0 - 15*t), int(g0 - 15*t), int(b0 - 15*t)))
    return img


def _load_product_image(url: str) -> Optional[Image.Image]:
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
        img = ImageEnhance.Color(img).enhance(1.22)
        img = ImageEnhance.Contrast(img).enhance(1.08)
        img = ImageEnhance.Sharpness(img).enhance(1.15)
        img = ImageEnhance.Brightness(img).enhance(1.04)
        return img
    except Exception as e:
        logger.warning(f"Could not load product image {url[:60]}: {e}")
        return None


def _compose_frame(
    bg: Image.Image,
    product_img: Image.Image,
    title: str,
    price: str,
    url: str,
    fmt: Dict,
    product_scale: float = 1.0,
    show_url: bool = False,
    x_offset: float = 0.0,
    y_offset: float = 0.0,
    angle: float = 0.0,
) -> Image.Image:
    w, h   = VIDEO_W, VIDEO_H
    canvas = bg.copy()

    # Fill the screen with the product image
    pw, ph  = product_img.size
    base_sc = max(h / ph, w / pw)  # Cover the entire frame
    cur_sc  = base_sc * product_scale
    nw, nh  = max(1, int(pw * cur_sc)), max(1, int(ph * cur_sc))
    
    fg = product_img.resize((nw, nh), Image.LANCZOS)
    
    if angle != 0:
        fg = fg.rotate(angle, resample=Image.BICUBIC, expand=True)
    
    # Paste centered with offset
    fw, fh = fg.size
    x_pos = (w - fw) // 2 + int(x_offset)
    y_pos = (h - fh) // 2 + int(y_offset)
    
    if fg.mode == "RGBA":
        canvas.paste(fg, (x_pos, y_pos), fg)
    else:
        canvas.paste(fg, (x_pos, y_pos))

    # Transparent center overlay for text (Template N style)
    box_w = int(w * 0.85)
    box_h = int(h * 0.35)
    box_x = (w - box_w) // 2
    box_y = (h - box_h) // 2

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle([box_x, box_y, box_x + box_w, box_y + box_h], radius=20, fill=(0, 0, 0, 90))
    
    cvs = canvas.convert("RGBA")
    cvs.alpha_composite(overlay)
    img = cvs.convert("RGB")
    draw = ImageDraw.Draw(img)

    # CTA / Badge
    draw.text((w // 2, box_y + int(box_h * 0.15)), fmt.get("cta", "SHOP NOW").upper(), fill="white", font=_font(int(box_h * 0.06)), anchor="mm")

    # Title
    for i, line in enumerate(textwrap.wrap(title, 34)[:2]):
        draw.text((w // 2, box_y + int(box_h * 0.40) + i * int(box_h * 0.12)), line, fill="white", font=_font(int(box_h * 0.08)), anchor="mm")

    # Price
    if price:
        draw.text((w // 2, box_y + int(box_h * 0.8)), f"${price}", fill=(255, 127, 80), font=_font(int(box_h * 0.09)), anchor="mm")

    # URL bar (last frame only)
    if show_url:
        short = url.replace("https://", "").split("?")[0][:44]
        draw.rounded_rectangle([(35, h-62), (w-35, h-14)], radius=14, fill=(255, 255, 255, 190))
        draw.text((w//2, h-38), short, font=_font(22, bold=False), fill=(0, 70, 180), anchor="mm")

    return img


def _save_thumbnail(frame_img: Image.Image, handle: str) -> str:
    """Save first composed frame as a JPEG thumbnail. Returns path."""
    thumb_path = str(OUT_DIR / f"{handle[:30]}_thumb.jpg")
    frame_img.convert("RGB").save(thumb_path, "JPEG", quality=92)
    logger.info(f"Thumbnail saved: {thumb_path}")
    return thumb_path


def _pick_music_track() -> Optional[str]:
    """Pick a random MP3 from audio folder. Returns path or None."""
    if not _AUDIO_DIR.exists():
        return None
    tracks = [f for f in glob.glob(str(_AUDIO_DIR / "*.mp3"))
              if os.path.getsize(f) > 50_000]
    if tracks:
        return random.choice(tracks)
    return None


def _static_frame_clip(
    frame_img: Image.Image,
    duration: float,
) -> VideoClip:
    """Create a static video clip from a single PIL image."""
    frame_array = np.array(frame_img)
    return VideoClip(lambda t: frame_array, duration=duration).set_fps(FPS)


def _slide_clip(
    bg: Image.Image,
    product_img: Image.Image,
    title: str,
    price: str,
    url: str,
    fmt: Dict,
    effect: str,
    show_url: bool = False,
) -> VideoClip:
    import math
    
    # Background is already blurred and prepared
    bg_r = bg

    def _params(t: float):
        scale = 1.05  # slightly zoomed in to allow panning without showing edges
        ox, oy = 0, 0
        progress = t / CLIP_DURATION
        
        if effect == "zoom_in":
            scale = 1.0 + (progress * 0.1) # 1.0 to 1.1
        elif effect == "zoom_out":
            scale = 1.1 - (progress * 0.1) # 1.1 to 1.0
        elif effect == "slide_left":
            ox = 50 - (progress * 100)
        elif effect == "slide_right":
            ox = -50 + (progress * 100)
        elif effect == "slide_up":
            oy = 50 - (progress * 100)
        elif effect == "slide_down":
            oy = -50 + (progress * 100)
            
        return scale, ox, oy, 0

    def make_frame(t: float):
        scale, ox, oy, angle = _params(t)
        frame = _compose_frame(bg_r, product_img, title, price, url, fmt,
                               product_scale=scale,
                               show_url=show_url,
                               x_offset=ox, y_offset=oy, angle=angle)
        return np.array(frame)

    return VideoClip(make_frame, duration=CLIP_DURATION).set_fps(FPS)


def build_video(product: Dict, fmt: Dict, bg_colors: List[tuple], store_base_url: str) -> Optional[Tuple[str, str]]:
    """
    Build a 30s product slideshow mp4 from Shopify product images.
    Returns tuple (video_path, thumbnail_path) or None on failure.
    """
    title  = product["title"]
    price  = product.get("variants", [{}])[0].get("price", "0")
    handle = product.get("handle", "")
    url    = f"{store_base_url.rstrip('/')}/products/{handle}?utm_source=pinterest&utm_medium=video&utm_campaign={BRAND_NAME.lower()}"

    images = product.get("images", [])
    if not images:
        logger.error(f"No images for product {title}")
        return None

    logger.info(f"Building video: {title[:50]} ({len(images)} slides)")

    effects = ["float", "wobble", "spin", "zoom-float"]
    clips   = []
    thumb_path = None
    intro_clip = None

    for i, img_data in enumerate(images):
        prod_img = _load_product_image(img_data["src"])
        if prod_img is None:
            continue
            
        from PIL import ImageFilter
        bg_r = prod_img.resize((VIDEO_W, VIDEO_H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(30)).point(lambda p: p * 0.6)
        
        effects  = ["zoom_in", "zoom_out", "slide_left", "slide_right", "slide_up", "slide_down"]
        effect   = effects[i % len(effects)]
        show_url = (i == len(images) - 1)
        clip     = _slide_clip(bg_r, prod_img, title, price, url, fmt, effect, show_url)
        clips.append(clip)

        # Save thumbnail from first image
        if thumb_path is None:
            intro_frame_img = _compose_frame(bg_r, prod_img, title, price, url, fmt, product_scale=1.0, show_url=False)
            thumb_path = _save_thumbnail(intro_frame_img, handle)

    if not clips:
        logger.error("No clips built — all product images failed to load")
        return None

    import math
    if clips and (len(clips) * CLIP_DURATION) < 5.0:
        loops = int(math.ceil(5.0 / (len(clips) * CLIP_DURATION)))
        clips = clips * loops

    video       = concatenate_videoclips(clips, method="compose")
    total_secs  = video.duration
    audio_clips = []

    # Background music
    music_path = _pick_music_track()
    if music_path:
        bg_aud = AudioFileClip(music_path).volumex(0.35)
        if bg_aud.duration < total_secs:
            bg_aud = bg_aud.audio_loop(duration=total_secs)
        else:
            bg_aud = bg_aud.subclip(0, total_secs)
        audio_clips.append(bg_aud)
        logger.info(f"Background music: {os.path.basename(music_path)}")

    # Voiceover (gTTS) — overlaid at end as CTA
    vo_text = (
        f"Discover the {title} at {BRAND_NAME} — only ${price}! "
        f"Shop the link in description now!"
    )
    try:
        pass
    except Exception:
        pass

    with tempfile.TemporaryDirectory() as tmp:
        vo_path = os.path.join(tmp, "vo.mp3")
        try:
            gTTS(text=vo_text, lang="en", tld="us").save(vo_path)
            vo = AudioFileClip(vo_path)
            if vo.duration > VOICEOVER_DURATION:
                vo = vo.subclip(0, VOICEOVER_DURATION)
            vo_start = max(0, total_secs - vo.duration - 1.0)
            audio_clips.append(vo.set_start(vo_start).volumex(1.1))
            logger.info(f"Voiceover: {vo.duration:.1f}s starting at {vo_start:.1f}s (end CTA)")
        except Exception as e:
            logger.warning(f"gTTS voiceover failed: {e}")

        if audio_clips:
            video = video.set_audio(CompositeAudioClip(audio_clips))

        out_path = str(OUT_DIR / f"{handle[:30]}_{int(time.time())}.mp4")
        logger.info(f"Rendering → {out_path}")
        video.write_videofile(
            out_path, fps=FPS, codec="libx264", audio_codec="aac",
            temp_audiofile=os.path.join(tmp, "tmp_audio.m4a"),
            remove_temp=True, verbose=False, logger=None,
            ffmpeg_params=["-crf", "18", "-preset", "fast", "-b:a", "192k"],
        )

    video.close()
    size_mb = os.path.getsize(out_path) / 1_048_576
    logger.info(f"Rendered: {os.path.basename(out_path)} ({size_mb:.1f} MB)")
    if size_mb > MAX_VIDEO_SIZE_MB:
        logger.error(f"Video too large ({size_mb:.1f} MB > {MAX_VIDEO_SIZE_MB} MB) — skipping")
        os.unlink(out_path)
        if thumb_path and os.path.exists(thumb_path):
            os.unlink(thumb_path)
        return None

    return (out_path, thumb_path)

def generate_reel_video(product: dict, output_path: str = "output/generated_reel.mp4", theme_index: int = None) -> str:
    brand_name = get_secret("BRAND_NAME", default="MEEESHOP").upper()
    public_domain = get_secret("PUBLIC_STORE_DOMAIN", default="us.meeeshop.com")
    
    fmt = FORMATS[theme_index % len(FORMATS)] if theme_index is not None else random.choice(FORMATS)
    bg_colors = SOLID_BG_COLORS
    
    # ensure images are properly formatted
    if "images" in product and product["images"] and isinstance(product["images"][0], str):
        product["images"] = [{"src": url} for url in product["images"]]
        
    result = build_video(product, fmt, bg_colors, public_domain)
    if result:
        out_path, thumb = result
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        import shutil
        shutil.move(out_path, output_path)
        return output_path
    return None
