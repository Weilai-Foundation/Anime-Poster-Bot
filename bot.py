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

    def get_theme_color(self, img, title=""):
        # Fixed Pink theme as per reference
        return (255, 172, 190)

    # ================= BANNER =================
    def create_banner(self, data):
        if not data:
            return None

        W, H = self.width, self.height
        img = Image.new("RGB", (W, H), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Theme Color
        theme_color = self.get_theme_color(None)

        # 1. Media Image (Right Side)
        url = (data.get("coverImage") or {}).get("extraLarge") or data.get("bannerImage")
        if url:
            media_img = self.download(url)
            if media_img:
                media_img = media_img.convert("RGB")
                # Fill the right half
                target_w, target_h = W // 2, H
                img_ratio = media_img.width / media_img.height
                target_ratio = target_w / target_h

                if img_ratio > target_ratio:
                    new_width = int(target_ratio * media_img.height)
                    left = (media_img.width - new_width) // 2
                    media_img = media_img.crop((left, 0, left + new_width, media_img.height))
                else:
                    new_height = int(media_img.width / target_ratio)
                    top = (media_img.height - new_height) // 2
                    media_img = media_img.crop((0, top, media_img.width, top + new_height))

                media_img = media_img.resize((target_w, target_h), Image.Resampling.LANCZOS)
                img.paste(media_img, (W // 2, 0))

        # 2. Decorations (Circles)
        draw.ellipse([-250, -250, 250, 250], fill=theme_color) # Top-left
        draw.ellipse([600, -150, 900, 150], fill=theme_color)  # Top-center
        draw.ellipse([-100, 600, 300, 1000], fill=theme_color) # Bottom-left

        # 3. Top Border
        draw.line((0, 5, W, 5), fill=theme_color, width=10)

        # 4. White vertical line (Left side)
        draw.line((40, 50, 40, 640), fill=(255, 255, 255), width=2)

        # 5. Top Left Branding
        # Vertical bar
        draw.rectangle((35, 120, 45, 250), fill=theme_color)
        # Horizontal line
        draw.line((35, 225, 325, 225), fill=theme_color, width=5)
        # Text
        draw.text((60, 180), "MANGA SARROWS", font=self.font(30, True), fill=(255, 255, 255))

        # 6. Title
        title_dict = data.get("title") or {}
        title = (title_dict.get("english") or title_dict.get("romaji") or "UNKNOWN").upper()

        font_size = 70
        title_font = self.font(font_size, True)
        lines = textwrap.wrap(title, width=20)

        y = 250
        for line in lines[:3]:
            draw.text((60, y), line, font=title_font, fill=(255, 255, 255))
            y += font_size + 5

        # 7. Genres
        # Lines
        draw.line((45, 480, 635, 480), fill=theme_color, width=5)
        draw.line((45, 555, 635, 555), fill=theme_color, width=5)
        # Text
        genre_list = [g.upper() for g in (data.get("genres") or [])[:3]]
        genre_font = self.font(34, True)
        gx = 60
        for g in genre_list:
            draw.text((gx, 495), g, font=genre_font, fill=(255, 255, 255))
            bbox = draw.textbbox((0, 0), g, font=genre_font)
            gx += (bbox[2] - bbox[0]) + 70

        # 8. Description
        desc = self.clean(data.get("description") or "No description available.")
        desc_y = 570
        for line in textwrap.wrap(desc, width=65)[:4]:
            draw.text((60, desc_y), line, font=self.font(16), fill=(255, 255, 255))
            desc_y += 22

        # 9. Bottom Branding (Footer)
        # JOIN NOW Box
        draw.rectangle((210, 670, 365, 715), fill=(255, 255, 255))
        draw.text((220, 675), "JOIN NOW", font=self.font(24, True), fill=(0, 0, 0))

        draw.text((385, 665), "MANGA SARROWS", font=self.font(34, True), fill=(255, 255, 255))
        draw.line((385, 698, 645, 698), fill=theme_color, width=5)

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
