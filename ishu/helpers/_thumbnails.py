import asyncio
import colorsys
import os
from pathlib import Path

import aiohttp
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from ishu import config
from ishu.helpers._dataclass import Track

try:
    from unidecode import unidecode
except ImportError:
    def unidecode(text):
        return text

_HELP_DIR = Path(__file__).parent
FONT_TITLE_PATH = str(_HELP_DIR / "Raleway-Bold.ttf")
FONT_INFO_PATH = str(_HELP_DIR / "Inter-Light.ttf")


def safe_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        # Fallback to standard system fonts
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/Library/Fonts/Arial Bold.ttf",
            "/Library/Fonts/Arial.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/arial.ttf",
        ]
        for sys_path in candidates:
            try:
                return ImageFont.truetype(sys_path, size)
            except Exception:
                pass
        return ImageFont.load_default()


def _fmt(sec):
    try:
        sec = int(sec)
    except (TypeError, ValueError):
        return "0:00"
    m, s = divmod(sec, 60)
    if m >= 60:
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def rounded_mask(size, radius):
    mask = Image.new("L", size, 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
    return mask


def fit_square(img: Image.Image, size: int) -> Image.Image:
    return ImageOps.fit(img, (size, size), method=Image.Resampling.LANCZOS)


def truncate_text(draw, text, font, max_width):
    if draw.textlength(text, font=font) <= max_width:
        return text
    lo, hi = 1, len(text)
    best = "..."
    while lo <= hi:
        mid = (lo + hi) // 2
        cand = text[:mid].rstrip() + "..."
        if draw.textlength(cand, font=font) <= max_width:
            best = cand
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def create_horizontal_gradient(size, color1, color2, color3):
    w, h = size
    tiny = Image.new("RGB", (3, 1))
    tiny.putpixel((0, 0), color1)
    tiny.putpixel((1, 0), color2)
    tiny.putpixel((2, 0), color3)
    return tiny.resize((w, h), Image.Resampling.BILINEAR).convert("RGBA")


def get_vibrant_colors(image, num_colors=3):
    # Resize heavily to speed up quantization and average out noise
    small_image = image.resize((50, 50)).convert("RGB")
    q = small_image.quantize(colors=num_colors, method=Image.Quantize.MAXCOVERAGE)
    palette = q.getpalette()
    
    vibrant_colors = []
    for i in range(num_colors):
        r, g, b = palette[i*3 : i*3+3]
        h, s, v = colorsys.rgb_to_hsv(r/255.0, g/255.0, b/255.0)
        # Boost saturation and brightness for a glowing neon effect
        s = min(1.0, s * 1.5 + 0.3)
        v = min(1.0, v * 1.5 + 0.3)
        r_n, g_n, b_n = colorsys.hsv_to_rgb(h, s, v)
        vibrant_colors.append((int(r_n * 255), int(g_n * 255), int(b_n * 255)))
    
    # If it extracted less colors than we wanted, duplicate the last one
    while len(vibrant_colors) < num_colors:
        vibrant_colors.append(vibrant_colors[-1] if vibrant_colors else (0, 255, 255))
        
    return vibrant_colors


def draw_gradient_border(canvas, box, radius, width, color1, color2, color3, blur=0):
    x1, y1, x2, y2 = box
    w = x2 - x1
    h = y2 - y1
    
    # Create border mask
    mask = Image.new("L", (w, h), 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.rounded_rectangle((0, 0, w, h), radius=radius, outline=255, width=width)
    
    # Create gradient of the card size
    grad = create_horizontal_gradient((w, h), color1, color2, color3)
    
    # Create a transparent layer of the canvas size
    W, H = canvas.size
    border_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    
    # Paste the gradient on border layer using mask
    border_layer.paste(grad, (x1, y1), mask)
    
    if blur > 0:
        border_layer = border_layer.filter(ImageFilter.GaussianBlur(blur))
        
    canvas.alpha_composite(border_layer)


def draw_shuffle_icon(draw, center, color=(140, 255, 70)):
    cx, cy = center
    draw.line([(cx - 10, cy - 8), (cx - 3, cy - 8), (cx + 3, cy + 8), (cx + 10, cy + 8)], fill=color, width=3)
    draw.line([(cx - 10, cy + 8), (cx - 3, cy + 8), (cx + 3, cy - 8), (cx + 10, cy - 8)], fill=color, width=3)
    draw.polygon([(cx + 6, cy - 11), (cx + 12, cy - 8), (cx + 6, cy - 5)], fill=color)
    draw.polygon([(cx + 6, cy + 5), (cx + 12, cy + 8), (cx + 6, cy + 11)], fill=color)


def draw_repeat_icon(draw, center, color=(255, 200, 40)):
    cx, cy = center
    draw.arc([cx - 9, cy - 9, cx + 9, cy + 9], start=45, end=315, fill=color, width=3)
    draw.polygon([(cx + 3, cy - 11), (cx + 10, cy - 7), (cx + 5, cy - 3)], fill=color)


def draw_prev_icon(draw, center, color=(255, 255, 255)):
    cx, cy = center
    draw.rectangle([cx - 10, cy - 8, cx - 7, cy + 8], fill=color)
    draw.polygon([(cx - 6, cy), (cx + 6, cy - 8), (cx + 6, cy + 8)], fill=color)


def draw_pause_icon(draw, center, color=(255, 255, 255)):
    cx, cy = center
    draw.rectangle([cx - 6, cy - 9, cx - 2, cy + 9], fill=color)
    draw.rectangle([cx + 2, cy - 9, cx + 6, cy + 9], fill=color)


def draw_next_icon(draw, center, color=(255, 255, 255)):
    cx, cy = center
    draw.polygon([(cx + 6, cy), (cx - 6, cy - 8), (cx - 6, cy + 8)], fill=color)
    draw.rectangle([cx + 7, cy - 8, cx + 10, cy + 8], fill=color)


def draw_heart_icon(draw, center, color=(255, 60, 90)):
    cx, cy = center
    draw.ellipse([cx - 9, cy - 8, cx, cy + 1], fill=color)
    draw.ellipse([cx, cy - 8, cx + 9, cy + 1], fill=color)
    draw.polygon([(cx - 9, cy - 3), (cx + 9, cy - 3), (cx, cy + 9)], fill=color)


def draw_headphones_icon(draw, center, color=(255, 255, 255)):
    cx, cy = center
    draw.arc([cx - 9, cy - 9, cx + 9, cy + 9], start=180, end=360, fill=color, width=3)
    draw.rounded_rectangle([cx - 11, cy, cx - 7, cy + 9], radius=2, fill=color)
    draw.rounded_rectangle([cx + 7, cy, cx + 11, cy + 9], radius=2, fill=color)
    draw.line([(cx - 9, cy), (cx - 9, cy + 3)], fill=color, width=3)
    draw.line([(cx + 9, cy), (cx + 9, cy + 3)], fill=color, width=3)


def compress_jpeg_under_limit(img: Image.Image, output_path: str, max_bytes: int = 200 * 1024):
    for quality in [92, 88, 84, 80, 76, 72, 68, 64, 60]:
        img.save(output_path, "JPEG", quality=quality, optimize=True, progressive=True)
        if os.path.getsize(output_path) <= max_bytes:
            return output_path

    temp = img
    for width in [1024, 960, 800, 640]:
        height = int(width * 9 / 16)
        temp = img.resize((width, height), Image.Resampling.LANCZOS)
        for quality in [72, 66, 60, 54]:
            temp.save(output_path, "JPEG", quality=quality, optimize=True, progressive=True)
            if os.path.getsize(output_path) <= max_bytes:
                return output_path

    raise ValueError("Could not compress thumbnail under Telegram 200KB limit.")


class Thumbnail:
    WIDTH = 1280
    HEIGHT = 720

    def __init__(self):
        self.session = None

    async def start(self):
        self.session = aiohttp.ClientSession()
        os.makedirs("cache", exist_ok=True)
        _HELP_DIR.mkdir(parents=True, exist_ok=True)

        for font_path, url in [
            (FONT_TITLE_PATH, "https://cdn.jsdelivr.net/fontsource/fonts/raleway@latest/latin-700-normal.ttf"),
            (FONT_INFO_PATH, "https://cdn.jsdelivr.net/fontsource/fonts/inter@latest/latin-400-normal.ttf"),
        ]:
            if not os.path.exists(font_path):
                try:
                    headers = {"User-Agent": "Mozilla/5.0"}
                    async with self.session.get(url, headers=headers) as resp:
                        if resp.status == 200:
                            content = await resp.read()
                            with open(font_path, "wb") as f:
                                f.write(content)
                except Exception as e:
                    print(f"Error downloading font from {url}: {e}")
        return True

    async def close(self):
        if self.session:
            await self.session.close()

    async def save_thumb(self, output_path: str, url: str) -> str:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        for attempt in range(3):
            try:
                if url.startswith("http"):
                    async with aiohttp.ClientSession(headers=headers) as session:
                        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                            if resp.status == 200:
                                content = await resp.read()
                                with open(output_path, "wb") as f:
                                    f.write(content)
                                return output_path
            except Exception as e:
                if attempt == 2:
                    print(f"Error saving thumb: {e}")
                await asyncio.sleep(1)
        return output_path

    async def download_thumb(self, url: str, path: str):
        await self.save_thumb(path, url)

    def create_image(self, thumb_path, output, song):
        W, H = self.WIDTH, self.HEIGHT
        
        # Load fonts
        title_font = safe_font(FONT_TITLE_PATH, 56)
        artist_font = safe_font(FONT_INFO_PATH, 32)
        small_font = safe_font(FONT_INFO_PATH, 24)

        try:
            src = Image.open(thumb_path).convert("RGB")
        except Exception:
            src = Image.new("RGB", (W, H), (30, 30, 30))

        # Blurred Background
        bg_ratio = W / H
        src_ratio = src.width / src.height
        if src_ratio > bg_ratio:
            new_w = int(src.height * bg_ratio)
            offset = (src.width - new_w) // 2
            bg = src.crop((offset, 0, offset + new_w, src.height))
        else:
            new_h = int(src.width / bg_ratio)
            offset = (src.height - new_h) // 2
            bg = src.crop((0, offset, src.width, offset + new_h))

        bg = bg.resize((W, H), Image.Resampling.LANCZOS)
        bg = bg.filter(ImageFilter.GaussianBlur(24))
        bg = bg.convert("RGBA")

        # Dark overlay
        bg_overlay = Image.new("RGBA", (W, H), (0, 0, 0, 110))
        bg = Image.alpha_composite(bg, bg_overlay)

        canvas = bg.copy()

        # Dimensions & parameters
        card_x1, card_y1 = 110, 100
        card_x2, card_y2 = 1170, 620
        card_w = card_x2 - card_x1
        card_h = card_y2 - card_y1
        radius = 42

        # Extract vibrant neon colors dynamically from the album cover
        extracted_colors = get_vibrant_colors(src, 3)
        color_left = extracted_colors[0]
        color_mid = extracted_colors[1]
        color_right = extracted_colors[2]

        # Translucent glass panel background
        panel = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
        panel_draw = ImageDraw.Draw(panel)
        panel_draw.rounded_rectangle((0, 0, card_w, card_h), radius=radius, fill=(28, 22, 20, 160))

        # Glass blur effect
        panel_mask = rounded_mask((card_w, card_h), radius)
        panel_bg = canvas.crop((card_x1, card_y1, card_x2, card_y2)).filter(ImageFilter.GaussianBlur(12))
        panel_bg = panel_bg.convert("RGBA")
        panel_bg.alpha_composite(panel)
        canvas.paste(panel_bg, (card_x1, card_y1), panel_mask)

        # Outer card neon glow & border
        draw_gradient_border(canvas, (card_x1, card_y1, card_x2, card_y2), radius=42, width=12,
                             color1=color_left, color2=color_mid, color3=color_right, blur=18)
        draw_gradient_border(canvas, (card_x1, card_y1, card_x2, card_y2), radius=42, width=8,
                             color1=color_left, color2=color_mid, color3=color_right, blur=8)
        draw_gradient_border(canvas, (card_x1, card_y1, card_x2, card_y2), radius=42, width=3,
                             color1=color_left, color2=color_mid, color3=color_right, blur=0)

        # Album Art
        album_size = 430
        album_x = 155
        album_y = 145
        album = fit_square(src, album_size).convert("RGBA")

        # Rounded album crop
        album_rounded = Image.new("RGBA", (album_size, album_size), (0, 0, 0, 0))
        album_rounded.paste(album, (0, 0), rounded_mask((album_size, album_size), 30))
        canvas.alpha_composite(album_rounded, (album_x, album_y))

        # Album art neon border
        draw_gradient_border(canvas, (album_x, album_y, album_x + album_size, album_y + album_size), radius=30, width=8,
                             color1=color_right, color2=color_left, color3=color_mid, blur=10)
        draw_gradient_border(canvas, (album_x, album_y, album_x + album_size, album_y + album_size), radius=30, width=3,
                             color1=color_right, color2=color_left, color3=color_mid, blur=0)

        # Text Drawing Setup
        d = ImageDraw.Draw(canvas)
        text_x = 625
        text_w = card_x2 - 45 - text_x

        title = unidecode(str(song.title or "Unknown Track"))
        artist = unidecode(str(song.channel_name or "Music Bot"))

        # Truncate text if it exceeds max width
        safe_title = truncate_text(d, title, title_font, text_w)
        safe_artist = truncate_text(d, artist, artist_font, text_w)

        # Draw Title and Artist
        d.text((text_x, 205), safe_title, font=title_font, fill=(255, 255, 255))
        d.text((text_x, 285), safe_artist, font=artist_font, fill=(180, 180, 180))

        # Progress bar
        bar_x1 = 625
        bar_y = 390
        bar_x2 = 1125

        total = getattr(song, "duration_sec", None) or 0
        cur = getattr(song, "time", None) or 0

        if total > 0:
            progress = min(max(cur / total, 0.0), 1.0)
        else:
            progress = 0.0

        played_x = bar_x1 + int((bar_x2 - bar_x1) * progress)

        # Progress background and fill
        d.rounded_rectangle((bar_x1, bar_y, bar_x2, bar_y + 8), radius=4, fill=(185, 185, 185, 120))
        if played_x > bar_x1:
            d.rounded_rectangle((bar_x1, bar_y, played_x, bar_y + 8), radius=4, fill=color_mid)
        d.ellipse((played_x - 10, bar_y - 6, played_x + 14, bar_y + 14), fill=(255, 255, 255))

        # Playback time labels
        time_played = _fmt(cur or 0)
        time_total = song.duration or _fmt(total) or "0:00"

        # Format start duration to match minute padding of time_total
        if time_total and ":" in time_total:
            total_min_len = len(time_total.split(":")[0])
            played_min = time_played.split(":")[0]
            if total_min_len == 2 and len(played_min) == 1:
                time_played = "0" + time_played
            elif total_min_len == 1 and len(played_min) == 2 and time_played.startswith("0"):
                time_played = time_played[1:]

        d.text((bar_x1, bar_y + 25), time_played, font=small_font, fill=(210, 210, 210))
        tw = d.textbbox((0, 0), time_total, font=small_font)[2]
        d.text((bar_x2 - tw, bar_y + 25), time_total, font=small_font, fill=(210, 210, 210))

        # Vector Icon Row
        icons_y = 515
        draw_shuffle_icon(d, (625, icons_y), color=color_mid)
        draw_repeat_icon(d, (705, icons_y), color=color_left)
        draw_prev_icon(d, (785, icons_y))
        draw_pause_icon(d, (865, icons_y))
        draw_next_icon(d, (945, icons_y))
        draw_heart_icon(d, (1025, icons_y), color=color_right)
        draw_headphones_icon(d, (1105, icons_y))

        # Save and compress under 200KB limit
        final_img = canvas.convert("RGB")
        return compress_jpeg_under_limit(final_img, output)

    async def generate(self, song: Track) -> str:
        try:
            if not self.session:
                await self.start()

            cur_time = getattr(song, "time", 0) or 0
            temp = f"cache/temp_{song.id}_{cur_time}.jpg"
            output = f"cache/{song.id}_{cur_time}.jpg"

            if os.path.exists(output):
                return output

            await self.download_thumb(song.thumbnail, temp)
            await asyncio.to_thread(self.create_image, temp, output, song)

            if os.path.exists(temp):
                os.remove(temp)

            return output

        except Exception as e:
            print(f"Error generating thumbnail: {e}")
            import traceback
            traceback.print_exc()
            return config.DEFAULT_THUMB
