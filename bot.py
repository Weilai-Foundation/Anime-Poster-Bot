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
    "8795689757:AAF5zQONtSnlrJr0y0W0JxfuvB9Cn2uNnFg"  # your token (kept)
)

ANILIST_API = "https://graphql.anilist.co"


# ================= GENERATOR =================
class BannerMaker:

    def __init__(self):
        self.width = 1280
        self.height = 500

    def search(self, name):
        query = """
        query ($search: String) {
          Media(search: $search, type: MANGA) {
            title { romaji english }
            description
            bannerImage
            coverImage { extraLarge }
            genres
          }
        }
        """
        res = requests.post(ANILIST_API, json={"query": query, "variables": {"search": name}})
        return res.json()["data"]["Media"]

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
        return Image.open(BytesIO(requests.get(url).content))

    # ================= MAIN BANNER =================
    def create_banner(self, data):
        W, H = self.width, self.height
        img = Image.new("RGB", (W, H), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        # ========= RIGHT IMAGE =========
        url = data.get("bannerImage") or data["coverImage"]["extraLarge"]
        right = self.download(url).resize((600, 500))
        img.paste(right, (680, 0))

        # ========= DARK FADE =========
        fade = Image.new("RGBA", (W, H))
        for x in range(600, W):
            alpha = int(255 * (x - 600) / 680)
            for y in range(H):
                fade.putpixel((x, y), (0, 0, 0, min(alpha, 220)))
        img = Image.alpha_composite(img.convert("RGBA"), fade).convert("RGB")
        draw = ImageDraw.Draw(img)

        # ========= NEON BORDER =========
        neon = (0, 200, 255)
        draw.rectangle((0, 0, W-1, H-1), outline=neon, width=2)

        # ========= LEFT LINE =========
        draw.rectangle((30, 50, 34, H-50), fill=neon)

        # ========= TEXT =========
        title_font = self.font(70, True)
        small_font = self.font(18)
        tag_font = self.font(22, True)
        desc_font = self.font(18)

        # small title
        draw.text((60, 60), "MANHWA SORROWS", fill=(180, 180, 180), font=small_font)

        # main title
        title = data["title"]["english"] or data["title"]["romaji"]
        y = 100
        for line in textwrap.wrap(title.upper(), 18)[:2]:
            draw.text((60, y), line, font=title_font, fill=(255, 255, 255))
            y += 75

        # divider
        draw.line((60, y, 500, y), fill=neon, width=2)
        y += 15

        # genres
        x = 60
        for g in data["genres"][:3]:
            draw.text((x, y), g.upper(), font=tag_font, fill=(255, 255, 255))
            x += 160

        y += 35
        draw.line((60, y, 500, y), fill=neon, width=2)
        y += 15

        # description
        desc = self.clean(data["description"])
        for line in textwrap.wrap(desc, 70)[:4]:
            draw.text((60, y), line, font=desc_font, fill=(200, 200, 200))
            y += 22

        # ========= BUTTONS =========
        y += 20
        draw.rectangle((60, y, 170, y+40), fill=(255, 255, 255))
        draw.text((75, y+10), "JOIN NOW", fill=(0, 0, 0), font=tag_font)

        draw.rectangle((180, y, 360, y+40), outline=(100, 100, 100))
        draw.text((195, y+10), "MANHWA SORROWS", fill=(255, 255, 255), font=tag_font)

        return img


# ================= BOT =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send: /manhwa Solo Leveling")


async def manhwa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /manhwa name")
        return

    name = " ".join(context.args)
    msg = await update.message.reply_text("Creating banner...")

    try:
        gen = BannerMaker()
        data = gen.search(name)

        banner = gen.create_banner(data)

        bio = BytesIO()
        banner.save(bio, "PNG")
        bio.seek(0)

        await update.message.reply_photo(photo=bio)
        await msg.delete()

    except Exception as e:
        await msg.edit_text(f"Error: {e}")


# ================= MAIN =================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("manhwa", manhwa))

    print("Bot Running...")
    app.run_polling()


if __name__ == "__main__":
    main()
