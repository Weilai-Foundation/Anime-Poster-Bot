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
            return data.get("data", {}).get("Media")
        except Exception as e:
            print(f"Search Error: {e}")
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
        url = data.get("bannerImage") or (data.get("coverImage") and data["coverImage"].get("extraLarge"))
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
        draw.ellipse([-250, -250, 250, 250], fill=pink) # Top-left
        draw.ellipse([640 - 120, -180, 640 + 120, 60], fill=pink) # Top-center
        draw.ellipse([-120, 620, 200, 940], fill=pink) # Bottom-left

        # Vertical Line
        draw.line((40, 140, 40, 680), fill=(255, 255, 255), width=3)

        # Top Branding
        draw.line((30, 140, 60, 140), fill=pink, width=10)
        draw.text((60, 155), "MANGA SARROWS", font=self.font(34, True), fill=(255, 255, 255))
        draw.line((60, 205, 300, 205), fill=pink, width=6)

        # Title
        title_font = self.font(76, True)
        title_dict = data.get("title") or {}
        title = (title_dict.get("english") or title_dict.get("romaji") or "UNKNOWN")

        y = 250
        for line in textwrap.wrap(title.upper(), 16)[:2]:
            draw.text((60, y), line, font=title_font, fill=(255, 255, 255))
            y += 90

        # Genres
        draw.line((40, 470, 620, 470), fill=(255, 255, 255), width=2)
        genres = "     ".join([g.upper() for g in (data.get("genres") or [])[:3]])
        draw.text((60, 485), genres, font=self.font(34, True), fill=(255, 255, 255))

        # Description
        draw.line((40, 540, 620, 540), fill=(255, 255, 255), width=2)
        desc = self.clean(data.get("description") or "No description available.")
        y = 555
        for line in textwrap.wrap(desc, 68)[:4]:
            draw.text((60, y), line, font=self.font(16), fill=(255, 255, 255))
            y += 20

        # Bottom Branding
        draw.rectangle((200, 650, 320, 700), fill=(255, 255, 255))
        draw.text((212, 663), "JOIN NOW", font=self.font(20, True), fill=(0, 0, 0))
        draw.text((340, 660), "MANGA SARROWS", font=self.font(30, True), fill=(255, 255, 255))
        draw.line((340, 695, 580, 695), fill=pink, width=5)

        return img

    # ================= POSTER =================
    def create_poster(self, data):
        # Using the same layout for poster as it matches the requested photo
        return self.create_banner(data)


# ================= BOT =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome!\n\n"
        "/manhwa <name>\n"
        "/anime <name>"
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


async def manhwa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /manhwa <name>")
        return

    name = " ".join(context.args)
    msg = await update.message.reply_text(f"Searching: {name}...")

    gen = BannerMaker()
    data = gen.search(name, "MANGA")

    if not data:
        await msg.edit_text("Not found.")
        return

    await msg.edit_text("Generating...")
    banner = gen.create_banner(data)

    if not banner:
        await msg.edit_text("Failed.")
        return

    bio = BytesIO()
    banner.save(bio, "JPEG", quality=85, optimize=True)

    success = await send_with_retry(update, bio)

    if success:
        await msg.delete()
    else:
        await msg.edit_text("Failed to send image.")


async def anime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /anime <name>")
        return

    name = " ".join(context.args)
    msg = await update.message.reply_text(f"Searching: {name}...")

    gen = BannerMaker()
    data = gen.search(name, "ANIME")

    if not data:
        await msg.edit_text("Not found.")
        return

    await msg.edit_text("Generating...")
    poster = gen.create_poster(data)

    if not poster:
        await msg.edit_text("Failed.")
        return

    bio = BytesIO()
    poster.save(bio, "JPEG", quality=85, optimize=True)

    success = await send_with_retry(update, bio)

    if success:
        await msg.delete()
    else:
        await msg.edit_text("Failed to send image.")


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
    app.add_handler(CommandHandler("manhwa", manhwa))
    app.add_handler(CommandHandler("anime", anime))

    print("Bot Running...")
    app.run_polling()


if __name__ == "__main__":
    while True:
        try:
            main()
        except Exception as e:
            print("Restarting bot...", e)
