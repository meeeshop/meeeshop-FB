#!/usr/bin/env python3
"""
video_generator.py — Dynamic 6-Theme Vertical Video Reel Generator with Motion Effects, Music & Voiceover.

Features:
 - 6 distinct rotating visual Reel themes (9:16 vertical 1080x1920)
 - 4 Motion Animation Effects: float, wobble, spin, zoom-float (adapted from meeeshop-pinterest)
 - Version-agnostic MoviePy 1.x & 2.x imports & audio helpers
 - Random background music track selection from audio/ directory (34 tracks)
 - Text-to-speech voiceover generation (gTTS) overlaid on background music
 - Dynamic audio mixing (30% music + 115% voiceover volume)
 - 'FREE SHIPPING' callouts across all templates
"""

import os
import math
import random
import shutil
import logging
import requests
import tempfile
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from secrets_manager import get_secret

logger = logging.getLogger(__name__)

# Version-agnostic MoviePy imports
try:
    from moviepy.editor import ImageSequenceClip, AudioFileClip, CompositeAudioClip
except ImportError:
    try:
        from moviepy import ImageSequenceClip, AudioFileClip, CompositeAudioClip
    except ImportError:
        ImageSequenceClip = None
        AudioFileClip = None
        CompositeAudioClip = None


def set_volume(audio_clip, factor: float):
    if hasattr(audio_clip, 'volumex'):
        return audio_clip.volumex(factor)
    elif hasattr(audio_clip, 'with_volume'):
        return audio_clip.with_volume(factor)
    elif hasattr(audio_clip, 'multiply_volume'):
        return audio_clip.multiply_volume(factor)
    return audio_clip


def attach_audio(video_clip, audio_clip):
    if hasattr(video_clip, 'set_audio'):
        return video_clip.set_audio(audio_clip)
    elif hasattr(video_clip, 'with_audio'):
        return video_clip.with_audio(audio_clip)
    return video_clip


def trim_clip(clip, start_t: float, end_t: float):
    if hasattr(clip, 'subclip'):
        return clip.subclip(start_t, end_t)
    elif hasattr(clip, 'subclipped'):
        return clip.subclipped(start_t, end_t)
    return clip


def loop_audio(audio_clip, target_duration: float):
    if hasattr(audio_clip, 'loop'):
        return audio_clip.loop(duration=target_duration)
    elif hasattr(audio_clip, 'audio_loop'):
        return audio_clip.audio_loop(duration=target_duration)
    return audio_clip


def create_gradient(width: int, height: int, color1: tuple, color2: tuple) -> Image.Image:
    base = Image.new("RGBA", (width, height), color1)
    top = Image.new("RGBA", (width, height), color2)
    mask = Image.new("L", (width, height))
    mask_draw = ImageDraw.Draw(mask)
    for y in range(height):
        alpha = int(255 * (y / height))
        mask_draw.line([(0, y), (width, y)], fill=alpha)
    base.paste(top, (0, 0), mask)
    return base


def get_reel_fonts():
    try:
        f_brand = ImageFont.truetype("arialbd.ttf", 64)
        f_hook = ImageFont.truetype("arialbd.ttf", 54)
        f_price = ImageFont.truetype("arialbd.ttf", 72)
        f_cta = ImageFont.truetype("arialbd.ttf", 56)
        f_sub = ImageFont.truetype("arial.ttf", 36)
    except IOError:
        f_brand = ImageFont.load_default()
        f_hook = ImageFont.load_default()
        f_price = ImageFont.load_default()
        f_cta = ImageFont.load_default()
        f_sub = ImageFont.load_default()
    return f_brand, f_hook, f_price, f_cta, f_sub


REEL_THEMES = [
    {
        "name": "ootd_look",
        "bg_colors": ((248, 240, 235, 255), (250, 245, 235, 255)),
        "card_bg": (255, 255, 255, 255),
        "header_color": "#FFC832",
        "cta_color": "#FFC832",
        "text_color": "#111111",
        "accent_color": "#333333",
        "price_bg": "#FFC832",
        "hooks": ["🔥 OOTD | SHOP THE LOOK", "✨ DAILY STYLE INSPO", "🎁 FREE SHIPPING TODAY"]
    },
    {
        "name": "trending_now",
        "bg_colors": ((235, 248, 240, 255), (235, 245, 250, 255)),
        "card_bg": (255, 255, 255, 255),
        "header_color": "#FF3264",
        "cta_color": "#FF3264",
        "text_color": "#111111",
        "accent_color": "#222222",
        "price_bg": "#FF3264",
        "hooks": ["🔥 TRENDING | GET IT NOW", "⚡ VIRAL ON PINTEREST", "🎁 FREE SHIPPING INCLUDED"]
    },
    {
        "name": "new_drop",
        "bg_colors": ((30, 34, 42, 255), (45, 50, 60, 255)),
        "card_bg": (255, 255, 255, 255),
        "header_color": "#32C864",
        "cta_color": "#32C864",
        "text_color": "#FFFFFF",
        "accent_color": "#111111",
        "price_bg": "#32C864",
        "hooks": ["✨ NEW DROP | SHOP BEFORE IT'S GONE", "🔥 FRESH ARRIVALS", "🎁 FAST & FREE SHIPPING"]
    },
    {
        "name": "style_tips",
        "bg_colors": ((240, 235, 248, 255), (240, 240, 248, 255)),
        "card_bg": (255, 255, 255, 255),
        "header_color": "#50A0FF",
        "cta_color": "#50A0FF",
        "text_color": "#111111",
        "accent_color": "#222222",
        "price_bg": "#50A0FF",
        "hooks": ["💡 STYLE TIPS | SEE ALL STYLES", "⭐ TOP RATED 5.0 STARS", "🎁 FREE SHIPPING | SHOP NOW"]
    },
    {
        "name": "fashion_steal",
        "bg_colors": ((245, 238, 230, 255), (248, 240, 235, 255)),
        "card_bg": (255, 255, 255, 255),
        "header_color": "#FF8232",
        "cta_color": "#FF8232",
        "text_color": "#111111",
        "accent_color": "#333333",
        "price_bg": "#FF8232",
        "hooks": ["💰 FASHION STEAL | GRAB THIS DEAL", "🔥 LIMITED TIME OFFER", "🎁 FREE SHIPPING | ORDER TODAY"]
    },
    {
        "name": "romantic_era",
        "bg_colors": ((248, 235, 240, 255), (253, 240, 240, 255)),
        "card_bg": (255, 255, 255, 255),
        "header_color": "#731E46",
        "cta_color": "#731E46",
        "text_color": "#111111",
        "accent_color": "#4A142D",
        "price_bg": "#731E46",
        "hooks": ["💖 ROMANTIC ERA | ELEVATE YOUR LOOK", "✨ ESSENTIAL STYLE FAVORITE", "🎁 FREE SHIPPING | SHOP NOW"]
    }
]


def calculate_motion_params(t: float, effect: str):
    scale = 1.0
    if effect == "float":
        return scale + (t * 0.02), 0, int(math.cos(t * 3) * 15), math.sin(t * 2) * 2
    elif effect == "wobble":
        return scale + (t * 0.02), int(math.cos(t * 4) * 12), 0, math.sin(t * 4) * 3
    elif effect == "spin":
        return scale + (t * 0.03), 0, 0, t * 4
    elif effect == "zoom-float":
        return scale + (t * 0.04), 0, int(math.cos(t * 2) * 10), math.sin(t * 2) * 2
    else:
        return scale + (t * 0.02), 0, 0, 0


def render_theme_frame(raw_img: Image.Image, slide_index: int, total_slides: int, step_index: int, max_steps: int, product: dict, brand_name: str, public_domain: str, theme: dict, effect_name: str) -> Image.Image:
    width, height = 1080, 1920
    canvas = create_gradient(width, height, theme["bg_colors"][0], theme["bg_colors"][1])

    t = step_index / max_steps
    scale_factor, offset_x, offset_y, angle = calculate_motion_params(t, effect_name)

    card_w, card_h = 960, 1150
    card_x, card_y = 60 + offset_x, 320 + offset_y

    zoomed_w = max(10, int(raw_img.width * scale_factor))
    zoomed_h = max(10, int(raw_img.height * scale_factor))
    img_zoomed = raw_img.resize((zoomed_w, zoomed_h), Image.Resampling.LANCZOS)
    img_zoomed.thumbnail((card_w - 40, card_h - 40), Image.Resampling.LANCZOS)

    if angle != 0:
        img_zoomed = img_zoomed.rotate(angle, resample=Image.BICUBIC, expand=True)

    card = Image.new("RGBA", (card_w, card_h), theme["card_bg"])
    zw, zh = img_zoomed.size
    card.paste(img_zoomed, ((card_w - zw) // 2, (card_h - zh) // 2), img_zoomed)

    canvas.paste(card, (card_x, card_y))
    draw = ImageDraw.Draw(canvas)

    f_brand, f_hook, f_price, f_cta, f_sub = get_reel_fonts()

    title = product.get("title", "")
    price = f"${product.get('price', '0.00')}"

    draw.rounded_rectangle([60, 100, 1020, 200], radius=25, fill=theme["header_color"])
    text_color = "#000000" if theme["header_color"] in ("#FFC832", "#32C864", "#FF8232", "#50A0FF") else "#FFFFFF"
    draw.text((90, 126), f"✨ {brand_name}", fill=text_color, font=f_brand)

    hook_text = theme["hooks"][min(slide_index, len(theme["hooks"]) - 1)]
    draw.rounded_rectangle([60, 220, 1020, 290], radius=15, fill=theme["accent_color"])
    draw.text((150, 238), hook_text, fill="white", font=f_hook)

    price_text_color = "#000000" if theme["price_bg"] in ("#FFC832", "#32C864", "#FF8232", "#50A0FF") else "#FFFFFF"
    draw.rounded_rectangle([660, 1400, 1020, 1490], radius=25, fill=theme["price_bg"])
    draw.text((690, 1422), f"ONLY {price}", fill=price_text_color, font=f_price)

    draw.rounded_rectangle([90, 1410, 480, 1480], radius=20, fill=(18, 22, 36, 230))
    draw.text((110, 1432), "⭐ 5.0 (490+ Reviews)", fill="#FFD700", font=f_sub)

    display_title = title if len(title) <= 42 else title[:40] + "..."
    draw.rounded_rectangle([40, 1510, 1040, 1590], radius=15, fill=(0, 0, 0, 160))
    draw.text((60, 1530), display_title, fill="#FFFFFF", font=f_hook)

    draw.rounded_rectangle([60, 1680, 1020, 1790], radius=30, fill=theme["cta_color"])
    cta_text_color = "#000000" if theme["cta_color"] in ("#FFC832", "#32C864", "#FF8232", "#50A0FF") else "#FFFFFF"
    cta_display = f"🛒 SHOP NOW AT  {public_domain.upper()}"
    draw.text((120, 1718), cta_display, fill=cta_text_color, font=f_cta)

    progress_w = int(1080 * ((slide_index + 1) / total_slides))
    draw.rectangle([0, 0, progress_w, 15], fill="#FFD700")

    return canvas.convert("RGB")


def _pick_audio_track() -> str:
    search_paths = [
        Path(__file__).resolve().parent.parent / "audio",
        Path(__file__).resolve().parent / "audio",
        Path("audio")
    ]
    tracks = []
    for dir_path in search_paths:
        if dir_path.exists() and dir_path.is_dir():
            tracks.extend(list(dir_path.glob("*.mp3")) + list(dir_path.glob("*.wav")))
    
    if tracks:
        selected = str(random.choice(tracks))
        logger.info("Selected background music track: %s", os.path.basename(selected))
        return selected
    logger.warning("No audio tracks found in audio/ directory.")
    return None


def generate_reel_video(product: dict, output_path: str = "output/generated_reel.mp4", theme_index: int = None) -> str:
    if ImageSequenceClip is None:
        raise ImportError("moviepy is required for video generation. Run: pip install moviepy==1.0.3")

    brand_name = get_secret("BRAND_NAME", default="MEEESHOP").upper()
    public_domain = get_secret("PUBLIC_STORE_DOMAIN", default="us.meeeshop.com")
    
    title = product.get("title", "Featured Item")
    price = product.get("price", "0.00")

    img_urls = product.get("images", [])[:3]
    if not img_urls:
        raise ValueError("Product has no images available for video reel generation.")

    if theme_index is None or not (0 <= theme_index < len(REEL_THEMES)):
        theme = random.choice(REEL_THEMES)
    else:
        theme = REEL_THEMES[theme_index]

    effects = ["float", "wobble", "spin", "zoom-float"]
    selected_effect = random.choice(effects)
    logger.info("Selected Video Reel Theme: '%s' | Motion Effect: '%s'", theme["name"], selected_effect)

    temp_dir = "temp_reel_frames"
    os.makedirs(temp_dir, exist_ok=True)
    all_frame_files = []

    try:
        frame_counter = 0
        total_slides = len(img_urls)
        frames_per_slide = 15

        for slide_idx, url in enumerate(img_urls):
            res = requests.get(url, timeout=15)
            res.raise_for_status()
            raw_img = Image.open(BytesIO(res.content)).convert("RGBA")

            for step in range(frames_per_slide):
                frame_img = render_theme_frame(
                    raw_img=raw_img,
                    slide_index=slide_idx,
                    total_slides=total_slides,
                    step_index=step,
                    max_steps=frames_per_slide,
                    product=product,
                    brand_name=brand_name,
                    public_domain=public_domain,
                    theme=theme,
                    effect_name=selected_effect
                )

                frame_path = os.path.join(temp_dir, f"frame_{frame_counter:04d}.jpg")
                frame_img.save(frame_path, "JPEG", quality=95)
                all_frame_files.append(frame_path)
                frame_counter += 1

        clip = ImageSequenceClip(all_frame_files, fps=12)
        total_duration = clip.duration

        # ── AUDIO MIXING ENGINE ──────────────────────────────────────────────
        audio_tracks = []

        # 1. Background Music (30% volume)
        music_file = _pick_audio_track()
        if music_file:
            try:
                bg_music = set_volume(AudioFileClip(music_file), 0.30)
                if bg_music.duration < total_duration:
                    bg_music = loop_audio(bg_music, total_duration)
                else:
                    bg_music = trim_clip(bg_music, 0, total_duration)
                audio_tracks.append(bg_music)
                logger.info("Mixed background music track into Reel.")
            except Exception as e:
                logger.warning("Failed to mix background music: %s", str(e))

        # 2. Text-to-Speech Voiceover (gTTS)
        try:
            from gtts import gTTS
            vo_text = f"Discover the {title} at {brand_name} for only ${price}! Tap the link now for free shipping on all orders!"
            vo_temp_dir = tempfile.mkdtemp()
            vo_path = os.path.join(vo_temp_dir, "voiceover.mp3")
            
            gTTS(text=vo_text, lang="en", tld="us").save(vo_path)
            vo_audio = set_volume(AudioFileClip(vo_path), 1.15)
            
            if vo_audio.duration > total_duration:
                vo_audio = trim_clip(vo_audio, 0, total_duration)
                
            audio_tracks.append(vo_audio)
            logger.info("Successfully generated and mixed voiceover audio (gTTS).")
        except Exception as e:
            logger.warning("Voiceover generation skipped or failed: %s", str(e))

        # Combine audio tracks into clip
        if audio_tracks:
            clip = attach_audio(clip, CompositeAudioClip(audio_tracks))

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        clip.write_videofile(
            output_path, 
            fps=24, 
            codec="libx264", 
            audio_codec="aac", 
            temp_audiofile="temp_audio.m4a",
            remove_temp=True, 
            logger=None
        )

        logger.info("Successfully generated video Reel with Audio & Voiceover (%s): %s", theme['name'], output_path)
        return output_path

    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Multi-theme Reel video generator with Motion Effects, Audio & Voiceover ready.")
