# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic


import os
import aiohttp
from PIL import (Image, ImageDraw, ImageFont, ImageOps)

try:
    from ishu import config, logger
    from ishu.helpers import Track
except ImportError:
    from anony import config, logger
    from anony.helpers import Track

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PKG_DIR = os.path.dirname(BASE_DIR)
ASSETS_DIR = os.path.join(PKG_DIR, "assets")

TITANIC_TEMPLATE = os.path.join(ASSETS_DIR, "titanic_thumb.jpg")
FONT_RALEWAY = os.path.join(BASE_DIR, "Raleway-Bold.ttf")
FONT_HINDI = os.path.join(BASE_DIR, "NotoSansDevanagari-Bold.ttf")


class Thumbnail:
    def __init__(self):
        self.font1 = ImageFont.truetype(FONT_RALEWAY, 44) if os.path.exists(FONT_RALEWAY) else ImageFont.load_default()
        self.font2 = ImageFont.truetype(FONT_RALEWAY, 20) if os.path.exists(FONT_RALEWAY) else ImageFont.load_default()
        self.font_av = ImageFont.truetype(FONT_RALEWAY, 44) if os.path.exists(FONT_RALEWAY) else ImageFont.load_default()
        if os.path.exists(FONT_HINDI):
            self.font_hindi = ImageFont.truetype(FONT_HINDI, 38)
        else:
            self.font_hindi = self.font1
        self.session: aiohttp.ClientSession | None = None
        self.template_path = TITANIC_TEMPLATE

    async def start(self) -> None:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def close(self) -> None:
        if self.session and not self.session.closed:
            await self.session.close()

    async def save_thumb(self, output_path: str, url: str) -> str:
        if self.session is None or self.session.closed:
            await self.start()
        async with self.session.get(url) as resp:
            with open(output_path, "wb") as f:
                f.write(await resp.read())
        return output_path

    async def generate(self, song: Track, size=(1024, 576)) -> str:
        try:
            os.makedirs("cache", exist_ok=True)
            user_suffix = str(getattr(song, "user_id", None) or "anon")
            output = f"cache/{song.id}_{user_suffix}.png"
            if os.path.exists(output):
                return output

            if not os.path.exists(self.template_path):
                return getattr(config, "DEFAULT_THUMB", None) or self.template_path

            temp = f"cache/temp_{song.id}.jpg"
            has_thumb = False
            if song.thumbnail:
                try:
                    await self.save_thumb(temp, song.thumbnail)
                    if os.path.exists(temp) and os.path.getsize(temp) > 0:
                        has_thumb = True
                except Exception as e:
                    logger.warning(f"Could not download song thumbnail: {e}")

            # Retrieve User Profile Picture
            is_autoplay = getattr(song, "user", None) == "Autoplay"
            user_avatar_path = (
                f"cache/user_{getattr(song, 'user_id', None)}.jpg"
                if getattr(song, "user_id", None)
                else "cache/user_autoplay.jpg" if is_autoplay
                else None
            )
            has_user_pfp = False
            if user_avatar_path and os.path.exists(user_avatar_path) and os.path.getsize(user_avatar_path) > 0:
                has_user_pfp = True
            elif is_autoplay or getattr(song, "user_photo", None) or getattr(song, "user_id", None):
                try:
                    try:
                        from ishu import app, userbot
                    except ImportError:
                        from anony import app, userbot

                    if is_autoplay:
                        # Try assistant profile picture first, then bot's profile picture
                        pfp_clients = []
                        if getattr(userbot, "clients", None):
                            pfp_clients.extend(userbot.clients)
                        pfp_clients.append(app)

                        for client in pfp_clients:
                            try:
                                async for photo in client.get_chat_photos("me", limit=1):
                                    await client.download_media(photo.file_id, file_name=user_avatar_path)
                                    if os.path.exists(user_avatar_path) and os.path.getsize(user_avatar_path) > 0:
                                        has_user_pfp = True
                                        break
                                if has_user_pfp:
                                    break
                            except Exception:
                                continue
                    elif getattr(song, "user_photo", None):
                        await app.download_media(getattr(song, "user_photo", None), file_name=user_avatar_path)
                    elif getattr(song, "user_id", None):
                        async for photo in app.get_chat_photos(getattr(song, "user_id", None), limit=1):
                            await app.download_media(photo.file_id, file_name=user_avatar_path)
                            break
                    if user_avatar_path and os.path.exists(user_avatar_path) and os.path.getsize(user_avatar_path) > 0:
                        has_user_pfp = True
                except Exception as err:
                    logger.warning(f"Could not download user avatar: {err}")

            base = Image.open(self.template_path).convert("RGBA")
            draw = ImageDraw.Draw(base)
            yellow = (255, 222, 3, 255)

            # Clear title and avatar area
            draw.rectangle((465, 230, 960, 385), fill=yellow)

            # Clear duration: 5:29 -> dynamic duration
            draw.rectangle((860, 408, 950, 438), fill=yellow)

            # Clear start time: 1:51 -> 0:00
            draw.rectangle((465, 408, 520, 438), fill=yellow)

            # Paste main song thumbnail on left box (88, 188)
            if has_thumb:
                try:
                    raw_thumb = Image.open(temp).convert("RGBA")
                    fitted = ImageOps.fit(
                        raw_thumb, (342, 332), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5)
                    )
                    mask = Image.new("L", (342 * 4, 332 * 4), 0)
                    d_mask = ImageDraw.Draw(mask)
                    d_mask.rounded_rectangle((0, 0, 342 * 4, 332 * 4), radius=32 * 4, fill=255)
                    mask = mask.resize((342, 332), Image.Resampling.LANCZOS)
                    base.paste(fitted, (88, 188), mask)
                except Exception as err:
                    logger.warning(f"Failed pasting song cover: {err}")
                finally:
                    if os.path.exists(temp):
                        try:
                            os.remove(temp)
                        except Exception:
                            pass

            # Paste User Profile Picture in enlarged box at (827, 245)
            box_size = (110, 110)
            radius = 22
            border = 4
            container = Image.new("RGBA", box_size, (0, 0, 0, 0))
            c_draw = ImageDraw.Draw(container)
            c_draw.rounded_rectangle(
                (0, 0, box_size[0], box_size[1]),
                radius=radius,
                fill=(255, 255, 255, 255),
            )

            inner_w = box_size[0] - border * 2
            inner_h = box_size[1] - border * 2

            if has_user_pfp:
                try:
                    pfp_img = Image.open(user_avatar_path).convert("RGBA")
                    fitted_pfp = ImageOps.fit(
                        pfp_img, (inner_w, inner_h), method=Image.Resampling.LANCZOS
                    )
                    inner_mask = Image.new("L", (inner_w, inner_h), 0)
                    m_draw = ImageDraw.Draw(inner_mask)
                    m_draw.rounded_rectangle(
                        (0, 0, inner_w, inner_h), radius=radius - 2, fill=255
                    )
                    container.paste(fitted_pfp, (border, border), inner_mask)
                except Exception as err:
                    logger.warning(f"Failed processing user pfp image: {err}")
                    has_user_pfp = False

            if not has_user_pfp:
                # Elegant fallback badge with user initial
                fallback_av = Image.new("RGBA", (inner_w, inner_h), (40, 40, 45, 255))
                f_draw = ImageDraw.Draw(fallback_av)
                raw_user_str = str(song.user or "U")
                # Remove HTML tags or mention symbols
                clean_name = "".join(
                    c for c in raw_user_str if c.isalnum() or c.isspace()
                ).strip()
                initial = clean_name[0].upper() if clean_name else "U"
                bbox = f_draw.textbbox((0, 0), initial, font=self.font_av)
                tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                f_draw.text(
                    ((inner_w - tw) // 2, (inner_h - th) // 2 - 4),
                    initial,
                    font=self.font_av,
                    fill=(255, 222, 3, 255),
                )
                inner_mask = Image.new("L", (inner_w, inner_h), 0)
                m_draw = ImageDraw.Draw(inner_mask)
                m_draw.rounded_rectangle(
                    (0, 0, inner_w, inner_h), radius=radius - 2, fill=255
                )
                container.paste(fallback_av, (border, border), inner_mask)

            base.paste(container, (827, 245), container)

            # Draw Title (support Hindi/Devanagari & Latin in large font size)
            title = song.title or "Unknown Track"
            is_hindi = any("\u0900" <= c <= "\u097f" for c in title)
            title_font = self.font_hindi if is_hindi else self.font1
            max_w = 345

            words = title.split()
            lines = []
            curr = ""
            for w in words:
                test_line = f"{curr} {w}".strip()
                if draw.textlength(test_line, font=title_font) <= max_w:
                    curr = test_line
                else:
                    if curr:
                        lines.append(curr)
                    curr = w
            if curr:
                lines.append(curr)

            if len(lines) > 2:
                lines = lines[:2]
                last = lines[-1]
                while (
                    draw.textlength(last + "...", font=title_font) > max_w
                    and len(last) > 1
                ):
                    last = last[:-1]
                lines[-1] = last + "..."

            y_text = 275 if len(lines) == 1 else 248
            line_height = 46 if is_hindi else 52
            for line in lines:
                draw.text((472, y_text), line, font=title_font, fill=(20, 20, 20, 255))
                y_text += line_height

            # Draw start time 0:00
            draw.text((472, 414), "0:00", font=self.font2, fill=(20, 20, 20, 255))

            # Draw Duration
            duration = str(song.duration or "03:00")
            draw.text((880, 414), duration, font=self.font2, fill=(20, 20, 20, 255))

            base.save(output, format="PNG")
            return output
        except Exception as err:
            logger.error(f"Thumbnail generation error: {err}")
            return self.template_path
