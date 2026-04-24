import os
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import textwrap
import re
import html

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

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
        self.height = 500

    # -------- API SEARCH --------
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

    # -------- CLEAN TEXT --------
    def clean(self, txt):
        return html.unescape(re.sub("<.*?>", "", txt or ""))

    # -------- FONT --------
    def font(self, size, bold=False):
        try:
            if bold:
                return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
            return ImageFont.truetype("DejaVuSans.ttf", size)
        except:
            return ImageFont.load_default()

    # -------- DOWNLOAD IMAGE --------
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
        img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
        draw = ImageDraw.Draw(img)

        # RIGHT IMAGE
        url = data.get("bannerImage") or (data.get("coverImage") and data["coverImage"].get("extraLarge"))
        if url:
            right = self.download(url)
            if right:
                right = right.convert("RGBA").resize((800, 500))
                img.paste(right, (480, 0))

        # FADE EFFECT
        mask = Image.new("L", (W, 1), 0)
        for x in range(480):
            mask.putpixel((x, 0), 255)
        for x in range(480, 800):
            alpha = int(255 * (1 - (x - 480) / 320))
            mask.putpixel((x, 0), alpha)

        mask = mask.resize((W, H))
        fade = Image.new("RGBA", (W, H), (0, 0, 0, 255))
        fade.putalpha(mask)

        img = Image.alpha_composite(img, fade).convert("RGB")
        draw = ImageDraw.Draw(img)

        # STYLE
        neon = (0, 200, 255)
        draw.rectangle((0, 0, W - 1, H - 1), outline=neon, width=2)
        draw.rectangle((30, 50, 34, H - 50), fill=neon)

        title_font = self.font(70, True)
        small_font = self.font(18)
        tag_font = self.font(22, True)
        desc_font = self.font(18)

        draw.text((60, 60), "MANHWA SORROWS", fill=(180, 180, 180), font=small_font)

        # TITLE
        title_dict = data.get("title") or {}
        title = (title_dict.get("english") or title_dict.get("romaji") or "UNKNOWN")[:40]

        y = 100
        for line in textwrap.wrap(title.upper(), 18)[:2]:
            draw.text((60, y), line, font=title_font, fill=(255, 255, 255))
            y += 75

        draw.line((60, y, 500, y), fill=neon, width=2)
        y += 15

        # GENRES
        x = 60
        for g in (data.get("genres") or [])[:3]:
            draw.text((x, y), g.upper(), font=tag_font, fill=(255, 255, 255))
            x += 160

        y += 35
        draw.line((60, y, 500, y), fill=neon, width=2)
        y += 15

        # DESCRIPTION
        desc = self.clean(data.get("description") or "No description available.")
        for line in textwrap.wrap(desc, 70)[:4]:
            draw.text((60, y), line, font=desc_font, fill=(200, 200, 200))
            y += 22

        # BUTTONS
        y += 20
        draw.rectangle((60, y, 170, y + 40), fill=(255, 255, 255))
        draw.text((75, y + 10), "JOIN NOW", fill=(0, 0, 0), font=tag_font)

        draw.rectangle((180, y, 360, y + 40), outline=(100, 100, 100))
        draw.text((195, y + 10), "MANHWA SORROWS", fill=(255, 255, 255), font=tag_font)

        return img

    # ================= POSTER =================
    def create_poster(self, data):
        if not data:
            return None

        W, H = 1280, 720
        img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
        draw = ImageDraw.Draw(img)

        url = data.get("bannerImage") or (data.get("coverImage") and data["coverImage"].get("extraLarge"))
        if url:
            right = self.download(url)
            if right:
                right = right.convert("RGBA").resize((900, 720))
                img.paste(right, (380, 0))

        neon = (0, 255, 150)
        draw.rectangle((0, 0, W - 1, H - 1), outline=neon, width=3)
        draw.rectangle((40, 60, 45, H - 60), fill=neon)

        title_font = self.font(80, True)
        tag_font = self.font(24, True)
        desc_font = self.font(20)

        title_dict = data.get("title") or {}
        title = (title_dict.get("english") or title_dict.get("romaji") or "UNKNOWN")[:40]

        y = 80
        for line in textwrap.wrap(title.upper(), 15)[:2]:
            draw.text((70, y), line, font=title_font, fill=(255, 255, 255))
            y += 90

        draw.line((70, y, 550, y), fill=neon, width=3)
        y += 20

        x = 70
        for g in (data.get("genres") or [])[:3]:
            draw.text((x, y), g.upper(), font=tag_font, fill=(255, 255, 255))
            x += 160

        y += 40
        draw.line((70, y, 550, y), fill=neon, width=3)
        y += 20

        desc = self.clean(data.get("description") or "No description available.")
        for line in textwrap.wrap(desc, 55)[:6]:
            draw.text((70, y), line, font=desc_font, fill=(220, 220, 220))
            y += 25

        return img.convert("RGB")


# ================= BOT =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome!\n\n"
        "/manhwa <name> - Create banner\n"
        "/anime <name> - Create poster"
    )


async def manhwa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /manhwa <name>")
        return

    name = " ".join(context.args)
    msg = await update.message.reply_text(f"Searching: {name}...")

    try:
        gen = BannerMaker()
        data = gen.search(name, "MANGA")

        if not data:
            await msg.edit_text("Not found.")
            return

        await msg.edit_text("Generating banner...")
        banner = gen.create_banner(data)

        if not banner:
            await msg.edit_text("Failed to generate image.")
            return

        bio = BytesIO()
        banner.save(bio, "PNG")
        bio.seek(0)

        await update.message.reply_photo(photo=bio)
        await msg.delete()

    except Exception as e:
        print(e)
        await msg.edit_text("Error occurred.")


async def anime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /anime <name>")
        return

    name = " ".join(context.args)
    msg = await update.message.reply_text(f"Searching: {name}...")

    try:
        gen = BannerMaker()
        data = gen.search(name, "ANIME")

        if not data:
            await msg.edit_text("Not found.")
            return

        await msg.edit_text("Generating poster...")
        poster = gen.create_poster(data)

        if not poster:
            await msg.edit_text("Failed to generate image.")
            return

        bio = BytesIO()
        poster.save(bio, "PNG")
        bio.seek(0)

        await update.message.reply_photo(photo=bio)
        await msg.delete()

    except Exception as e:
        print(e)
        await msg.edit_text("Error occurred.")


# ================= MAIN =================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("manhwa", manhwa))
    app.add_handler(CommandHandler("anime", anime))

    print("Bot Running...")
    app.run_polling()


if __name__ == "__main__":
    main()
