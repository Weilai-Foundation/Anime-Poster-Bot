import os
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import textwrap
import re
import html

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.request import HTTPXRequest

# ================= CONFIG =================
BOT_TOKEN = os.getenv(
    "BOT_TOKEN",
    "8795689757:AAF5zQONtSnlrJr0y0W0JxfuvB9Cn2uNnFg"
)

ANILIST_API = "https://graphql.anilist.co"


# ================= GENERATOR =================
class BannerMaker:

    def __init__(self):
        self.width = 1280
        self.height = 720

    def search(self, name, media_type="MANGA"):
        # Try AniList first
        data = self.search_anilist(name, media_type)
        if data:
            return data

        # If MANGA, try MangaDex then Jikan
        if media_type == "MANGA":
            data = self.search_mangadex(name)
            if data:
                return data
            data = self.search_jikan(name)
            if data:
                return data

        return None

    def search_anilist(self, name, media_type="MANGA"):
        query = """
        query ($search: String, $type: MediaType) {
          Media(search: $search, type: $type) {
            title { romaji english }
            description
            bannerImage
            coverImage { extraLarge }
            genres
          }
        }
        """
        try:
            res = requests.post(
                ANILIST_API,
                json={"query": query, "variables": {"search": name, "type": media_type}},
                timeout=10
            )
            res.raise_for_status()
            data = res.json()
            media = data.get("data", {}).get("Media")
            if media:
                return {
                    "title": media.get("title"),
                    "description": media.get("description"),
                    "coverImage": media.get("coverImage"),
                    "genres": media.get("genres")
                }
        except Exception as e:
            print(f"AniList Error: {e}")
        return None

    def search_mangadex(self, name):
        url = "https://api.mangadex.org/manga"
        params = {
            "title": name,
            "limit": 1,
            "includes[]": ["cover_art"]
        }
        try:
            res = requests.get(url, params=params, timeout=10)
            res.raise_for_status()
            data = res.json()
            if data["data"]:
                manga = data["data"][0]
                attr = manga["attributes"]

                # Title
                title_map = attr["title"]
                eng_title = title_map.get("en") or title_map.get("ja-ro") or list(title_map.values())[0]

                # Description
                desc_map = attr["description"]
                desc = desc_map.get("en") or (list(desc_map.values())[0] if desc_map else "")

                # Cover
                cover_file = ""
                for rel in manga["relationships"]:
                    if rel["type"] == "cover_art":
                        cover_file = rel.get("attributes", {}).get("fileName")
                        break

                cover_url = ""
                if cover_file:
                    cover_url = f"https://uploads.mangadex.org/covers/{manga['id']}/{cover_file}"

                return {
                    "title": {"english": eng_title, "romaji": None},
                    "description": desc,
                    "coverImage": {"extraLarge": cover_url},
                    "genres": [t["attributes"]["name"]["en"] for t in attr["tags"] if t["attributes"]["group"] == "genre"]
                }
        except Exception as e:
            print(f"MangaDex Error: {e}")
        return None

    def search_jikan(self, name):
        url = f"https://api.jikan.moe/v4/manga?q={name}&limit=1"
        try:
            res = requests.get(url, timeout=10)
            res.raise_for_status()
            data = res.json()
            if data["data"]:
                manga = data["data"][0]
                return {
                    "title": {"english": manga.get("title"), "romaji": manga.get("title_japanese")},
                    "description": manga.get("synopsis"),
                    "coverImage": {"extraLarge": manga["images"]["jpg"]["large_image_url"]},
                    "genres": [g["name"] for g in manga.get("genres", [])]
                }
        except Exception as e:
            print(f"Jikan Error: {e}")
        return None

    def clean(self, txt):
        return html.unescape(re.sub("<.*?>", "", txt or ""))

    def font(self, size, bold=False):
        try:
            if bold:
                return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
            return ImageFont.truetype("DejaVuSans.ttf", size)
        except:
            return ImageFont.load_default()

    def download(self, url):
        try:
            res = requests.get(url, timeout=10)
            res.raise_for_status()
            return Image.open(BytesIO(res.content))
        except:
            return None

    # ================= BANNER =================
    def create_banner(self, data):
        if not data:
            return None

        W, H = self.width, self.height
        img = Image.new("RGB", (W, H), (0, 0, 0))
        draw = ImageDraw.Draw(img)
        pink = (254, 194, 194)

        # Media Image (Right Side)
        url = (data.get("coverImage") or {}).get("extraLarge") or data.get("bannerImage")
        if url:
            right = self.download(url)
            if right:
                right = right.convert("RGB")
                # Center crop to 640x720
                target_w, target_h = 640, 720
                img_ratio = right.width / right.height
                target_ratio = target_w / target_h

                if img_ratio > target_ratio:
                    new_width = int(target_ratio * right.height)
                    left = (right.width - new_width) // 2
                    right = right.crop((left, 0, left + new_width, right.height))
                else:
                    new_height = int(right.width / target_ratio)
                    top = (right.height - new_height) // 2
                    right = right.crop((0, top, right.width, top + new_height))

                right = right.resize((target_w, target_h), Image.Resampling.LANCZOS)
                img.paste(right, (640, 0))

        # Decorations (Circles)
        draw.ellipse([-200, -200, 200, 200], fill=pink) # Top-left
        draw.ellipse([540, -100, 740, 100], fill=pink) # Top-center
        draw.ellipse([-100, 620, 100, 820], fill=pink) # Bottom-left

        # White Vertical Line
        draw.line((35, 40, 35, 680), fill=(255, 255, 255), width=2)

        # Top Branding
        draw.line((20, 40, 20, 140), fill=pink, width=10) # Corner Vertical
        draw.line((20, 40, 220, 40), fill=pink, width=10) # Corner Horizontal
        draw.text((60, 60), "MANGA SARROWS", font=self.font(28, True), fill=(255, 255, 255))
        draw.line((60, 100, 320, 100), fill=pink, width=4)

        # Title
        title_dict = data.get("title") or {}
        title = (title_dict.get("english") or title_dict.get("romaji") or "UNKNOWN").upper()

        font_size = 80
        lines = []
        title_font = self.font(font_size, True)
        while font_size >= 40:
            title_font = self.font(font_size, True)
            wrap_char_width = int(900 / font_size)
            lines = textwrap.wrap(title, wrap_char_width)

            max_w = 0
            for line in lines:
                bbox = draw.textbbox((0, 0), line, font=title_font)
                max_w = max(max_w, bbox[2] - bbox[0])

            if max_w <= 560 and len(lines) <= 3:
                break
            font_size -= 2

        y = 150
        for line in lines[:3]:
            draw.text((60, y), line, font=title_font, fill=(255, 255, 255))
            y += font_size + 5

        # Genres
        draw.line((50, 460, 610, 460), fill=(255, 255, 255), width=2)
        genre_list = [g.upper() for g in (data.get("genres") or [])[:3]]
        genre_font = self.font(28, True)
        gx = 60
        for g in genre_list:
            draw.text((gx, 475), g, font=genre_font, fill=(255, 255, 255))
            bbox = draw.textbbox((0, 0), g, font=genre_font)
            gx += (bbox[2] - bbox[0]) + 30 # Spacing
        draw.line((50, 520, 610, 520), fill=(255, 255, 255), width=2)

        # Description
        desc = self.clean(data.get("description") or "No description available.")
        y = 540
        for line in textwrap.wrap(desc, 65)[:3]:
            draw.text((60, y), line, font=self.font(18), fill=(255, 255, 255))
            y += 26

        # Bottom Branding
        draw.rectangle((180, 660, 310, 700), fill=(255, 255, 255))
        draw.text((195, 670), "JOIN NOW", font=self.font(18, True), fill=(0, 0, 0))
        draw.text((330, 665), "MANGA SARROWS", font=self.font(28, True), fill=(255, 255, 255))
        draw.line((330, 700, 560, 700), fill=pink, width=4)

        return img


# ================= BOT =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to MANGA SARROWS Bot!\n\n"
        "Commands:\n"
        "/manga <name> - Search for Manga\n"
        "/manhwa <name> - Search for Manhwa\n"
        "/manhua <name> - Search for Manhua\n"
        "/anime <name> - Search for Anime"
    )


async def send_with_retry(update, bio):
    for _ in range(2):
        try:
            bio.seek(0)
            await update.message.reply_photo(photo=bio)
            return True
        except Exception as e:
            print("Retry sending...", e)
    return False


async def search_media(update: Update, context: ContextTypes.DEFAULT_TYPE, media_type: str, cmd_name: str):
    if not context.args:
        await update.message.reply_text(f"Usage: /{cmd_name} <name>")
        return

    name = " ".join(context.args)
    msg = await update.message.reply_text(f"Searching {cmd_name}: {name}...")

    gen = BannerMaker()
    data = gen.search(name, media_type)

    if not data:
        await msg.edit_text(f"'{name}' not found.")
        return

    await msg.edit_text("Generating...")
    # Use create_banner for everything since they use the same style now
    img = gen.create_banner(data)

    if not img:
        await msg.edit_text("Failed to generate image.")
        return

    bio = BytesIO()
    img.save(bio, "JPEG", quality=90, optimize=True)

    success = await send_with_retry(update, bio)

    if success:
        await msg.delete()
    else:
        await msg.edit_text("Failed to send image.")

async def manga(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await search_media(update, context, "MANGA", "manga")

async def manhwa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await search_media(update, context, "MANGA", "manhwa")

async def manhua(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await search_media(update, context, "MANGA", "manhua")


async def anime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await search_media(update, context, "ANIME", "anime")


# ================= MAIN =================
def main():
    request = HTTPXRequest(
        connect_timeout=20.0,
        read_timeout=30.0,
        write_timeout=30.0,
        pool_timeout=10.0,
    )

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .request(request)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("manga", manga))
    app.add_handler(CommandHandler("manhwa", manhwa))
    app.add_handler(CommandHandler("manhua", manhua))
    app.add_handler(CommandHandler("anime", anime))

    print("Bot Running...")
    app.run_polling()


if __name__ == "__main__":
    while True:
        try:
            main()
        except Exception as e:
            print("Restarting bot...", e)
