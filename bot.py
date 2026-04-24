import os
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
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
        # Death Note Red theme
        return (229, 9, 20)

    def draw_gradient(self, img, W, H):
        draw = ImageDraw.Draw(img)
        # Approximate 135deg gradient from (0,0,0) to (17,17,17)
        # Using line drawing for better performance than pixel plotting
        for i in range(0, W + H, 2):
            factor = i / (W + H)
            val = int(17 * factor)
            draw.line([(i, 0), (0, i)], fill=(val, val, val), width=2)

    # ================= BANNER =================
    def create_banner(self, data):
        if not data:
            return None

        W, H = self.width, self.height
        img = Image.new("RGB", (W, H), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        # 1. Background Gradient
        self.draw_gradient(img, W, H)

        # 2. Layout split
        left_w = int(W * 0.55)
        right_w = W - left_w

        # 3. Media Image (Right Side)
        url = (data.get("coverImage") or {}).get("extraLarge") or data.get("bannerImage")
        if url:
            media_img = self.download(url)
            if media_img:
                media_img = media_img.convert("RGB")
                # Fill the right section
                target_w, target_h = right_w, H
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

                # Apply brightness filter (80%)
                enhancer = ImageEnhance.Brightness(media_img)
                media_img = enhancer.enhance(0.8)

                img.paste(media_img, (left_w, 0))

                # Gradient overlay (to left, from transparent to black)
                overlay = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
                overlay_draw = ImageDraw.Draw(overlay)
                for x in range(target_w):
                    alpha = int(255 * (1 - x / (target_w * 0.8))) # Fade out to the right
                    if alpha < 0: alpha = 0
                    overlay_draw.line((x, 0, x, target_h), fill=(0, 0, 0, alpha))
                img.paste(overlay, (left_w, 0), overlay)

        # 4. Red Accent Line (Left side)
        draw.rectangle((20, 30, 24, H - 30), fill=(179, 0, 0)) # #b30000

        # 5. Tag
        draw.text((50, 50), "MANGA COLLECTION", font=self.font(14), fill=(187, 187, 187)) # #bbb

        # 6. Title
        title_dict = data.get("title") or {}
        title = (title_dict.get("english") or title_dict.get("romaji") or "UNKNOWN").upper()

        title_y = 80
        for line in textwrap.wrap(title, width=20):
            draw.text((50, title_y), line, font=self.font(44, True), fill=(229, 9, 20)) # #e50914
            title_y += 50

        # 7. Subtitle
        romaji = title_dict.get("romaji")
        english = title_dict.get("english")
        subtitle = f"“{romaji}”" if romaji and english and romaji.lower() != english.lower() else ""

        # If no romaji-based subtitle, use a generic one instead of series-specific
        if not subtitle:
             subtitle = "“The Ultimate Collection”"

        draw.text((50, title_y + 10), subtitle, font=self.font(20), fill=(221, 221, 221)) # #ddd
        subtitle_bottom = title_y + 10 + 30

        # 8. Divider Line
        draw.line((50, subtitle_bottom + 10, 50 + int(left_w * 0.7), subtitle_bottom + 10), fill=(179, 0, 0), width=2)

        # 9. Categories/Genres
        genres = (data.get("genres") or [])[:3]
        gx = 50
        cat_y = subtitle_bottom + 45
        for g in genres:
            g_txt = g.upper()
            # Draw red "icon" placeholder
            draw.rectangle((gx, cat_y + 5, gx + 8, cat_y + 13), fill=(229, 9, 20))
            draw.text((gx + 15, cat_y), g_txt, font=self.font(14, True), fill=(255, 255, 255))
            bbox = draw.textbbox((gx + 15, cat_y), g_txt, font=self.font(14, True))
            gx = bbox[2] + 30

        # 10. Description
        desc = self.clean(data.get("description") or "No description available.")
        desc_y = cat_y + 45
        for line in textwrap.wrap(desc, width=60)[:5]:
            draw.text((50, desc_y), line, font=self.font(14), fill=(170, 170, 170)) # #aaa
            desc_y += 24

        # 11. Buttons
        btn_y = desc_y + 30
        # READ NOW
        draw.rectangle((50, btn_y, 180, btn_y + 45), fill=(229, 9, 20))
        draw.text((65, btn_y + 12), "READ NOW", font=self.font(14, True), fill=(255, 255, 255))

        # VIEW COLLECTION
        draw.rectangle((195, btn_y, 380, btn_y + 45), outline=(255, 255, 255), width=1)
        draw.text((210, btn_y + 12), "VIEW COLLECTION", font=self.font(14, True), fill=(255, 255, 255))

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
