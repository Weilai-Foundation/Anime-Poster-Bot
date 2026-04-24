import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from io import BytesIO
import textwrap
import re
import html
import math
import random

# Your Bot Token - Provided via environment variable
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("No BOT_TOKEN provided in environment variables")

# AniList API endpoint
ANILIST_API = "https://graphql.anilist.co"

class AnimePosterGenerator:
    def __init__(self):
        self.width = 1280
        self.height = 720
        
    def search_media(self, query, media_type="ANIME"):
        """Search media using AniList API"""
        graphql_query = """
        query ($search: String, $type: MediaType) {
          Media(search: $search, type: $type) {
            id
            title {
              romaji
              english
            }
            description
            coverImage {
              extraLarge
              large
            }
            bannerImage
            genres
            format
            episodes
            season
            seasonYear
            averageScore
            studios {
              nodes {
                name
              }
            }
          }
        }
        """
        
        variables = {"search": query, "type": media_type}
        response = requests.post(
            ANILIST_API,
            json={"query": graphql_query, "variables": variables}
        )
        
        if response.status_code == 200:
            return response.json()["data"]["Media"]
        return None

    def clean_html(self, text):
        """Remove HTML tags from text"""
        if not text:
            return ""
        clean = re.compile('<.*?>')
        text = re.sub(clean, '', text)
        return html.unescape(text)

    def draw_linear_gradient(self, draw, rect, color_start, color_end, horizontal=True):
        """Draw a linear gradient in a rectangle"""
        x1, y1, x2, y2 = rect
        if horizontal:
            for x in range(x1, x2):
                f = (x - x1) / (x2 - x1)
                r = int(color_start[0] + (color_end[0] - color_start[0]) * f)
                g = int(color_start[1] + (color_end[1] - color_start[1]) * f)
                b = int(color_start[2] + (color_end[2] - color_start[2]) * f)
                a = int(color_start[3] + (color_end[3] - color_start[3]) * f) if len(color_start) > 3 else 255
                draw.line([(x, y1), (x, y2)], fill=(r, g, b, a))
        else:
            for y in range(y1, y2):
                f = (y - y1) / (y2 - y1)
                r = int(color_start[0] + (color_end[0] - color_start[0]) * f)
                g = int(color_start[1] + (color_end[1] - color_start[1]) * f)
                b = int(color_start[2] + (color_end[2] - color_start[2]) * f)
                a = int(color_start[3] + (color_end[3] - color_start[3]) * f) if len(color_start) > 3 else 255
                draw.line([(x1, y), (x2, y)], fill=(r, g, b, a))

    def draw_radial_gradient(self, image, center, radius, color_inner, color_outer):
        """Draw a radial gradient onto an image"""
        cx, cy = center
        draw = ImageDraw.Draw(image)
        for r_curr in range(radius, 0, -1):
            f = r_curr / radius
            r = int(color_outer[0] + (color_inner[0] - color_outer[0]) * (1-f))
            g = int(color_outer[1] + (color_inner[1] - color_outer[1]) * (1-f))
            b = int(color_outer[2] + (color_inner[2] - color_outer[2]) * (1-f))
            a = int(color_outer[3] + (color_inner[3] - color_outer[3]) * (1-f)) if len(color_outer) > 3 else 255
            draw.ellipse([cx-r_curr, cy-r_curr, cx+r_curr, cy+r_curr], fill=(r, g, b, a))

    def draw_glow_shape(self, image, shape_func, color, glow_color, blur_radius):
        """Draw a shape with a glow effect"""
        # Create a layer for the glow
        glow_layer = Image.new('RGBA', image.size, (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow_layer)

        # Draw the base shape for the glow
        shape_func(glow_draw, glow_color)

        # Blur the glow layer
        glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(blur_radius))

        # Paste glow layer onto image
        image.paste(glow_layer, (0, 0), glow_layer)

        # Draw the main shape on top
        main_draw = ImageDraw.Draw(image)
        shape_func(main_draw, color)
    
    def download_image(self, url):
        """Download image from URL"""
        response = requests.get(url)
        return Image.open(BytesIO(response.content))
    
    def create_aesthetic_background(self):
        """Create aesthetic gradient background with patterns"""
        img = Image.new('RGB', (self.width, self.height))
        draw = ImageDraw.Draw(img)
        
        # Create smooth purple to deep blue gradient
        for y in range(self.height):
            # Smooth transition from purple to deep blue
            r = int(60 - (30 * y / self.height))
            g = int(40 - (20 * y / self.height))
            b = int(120 + (60 * y / self.height))
            draw.line([(0, y), (self.width, y)], fill=(r, g, b))
        
        return img
    
    def add_fireworks_effect(self, img):
        """Add colorful firework bursts"""
        overlay = Image.new('RGBA', (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        
        # Define firework positions and colors
        fireworks = [
            {'x': 650, 'y': 80, 'color': (255, 180, 100, 180), 'size': 80},
            {'x': 850, 'y': 120, 'color': (255, 100, 200, 180), 'size': 70},
            {'x': 750, 'y': 200, 'color': (100, 200, 255, 180), 'size': 60},
            {'x': 650, 'y': 280, 'color': (200, 100, 255, 180), 'size': 65},
            {'x': 550, 'y': 150, 'color': (100, 255, 200, 180), 'size': 55},
        ]
        
        for fw in fireworks:
            x, y = fw['x'], fw['y']
            color = fw['color']
            size = fw['size']
            
            # Draw starburst pattern
            for angle in range(0, 360, 12):
                end_x = x + int(size * math.cos(math.radians(angle)))
                end_y = y + int(size * math.sin(math.radians(angle)))
                
                # Thicker lines
                draw.line([(x, y), (end_x, end_y)], fill=color, width=3)
                
                # Add small circles at the end
                circle_size = 4
                draw.ellipse([end_x-circle_size, end_y-circle_size, 
                            end_x+circle_size, end_y+circle_size], fill=color)
        
        return Image.alpha_composite(img.convert('RGBA'), overlay)
    
    def _get_font(self, font_type, size):
        """Helper to get font from multiple possible paths"""
        bold_paths = [
            "DejaVuSans-Bold.ttf", # Local
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]
        regular_paths = [
            "DejaVuSans.ttf", # Local
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]

        paths = bold_paths if font_type == 'bold' else regular_paths

        for path in paths:
            try:
                return ImageFont.truetype(path, size)
            except:
                continue
        return ImageFont.load_default()

    def generate_poster(self, anime_data):
        """Generate anime poster"""
        # Create base
        base = self.create_aesthetic_background()
        
        # Add effects
        poster = self.add_fireworks_effect(base)
        poster = poster.convert('RGB')
        
        # Add anime cover on the right
        if anime_data.get('coverImage', {}).get('extraLarge'):
            cover = self.download_image(anime_data['coverImage']['extraLarge'])
            # Larger cover
            cover = cover.resize((450, 636), Image.Resampling.LANCZOS)
            
            # Position cover on the right
            cover_x = self.width - 480
            cover_y = (self.height - 636) // 2
            
            poster.paste(cover, (cover_x, cover_y), cover if cover.mode == 'RGBA' else None)
        
        # Add text overlay
        draw = ImageDraw.Draw(poster)
        
        # Get title
        title = anime_data['title'].get('english') or anime_data['title']['romaji']
        
        # Load fonts using helper
        title_font = self._get_font('bold', 90)
        info_font = self._get_font('regular', 38)
        small_font = self._get_font('regular', 32)
        logo_font = self._get_font('bold', 42)
        
        # Add ANIME MAYHEM logo at top
        draw.text((40, 30), "ANIME MAYHEM", font=logo_font, fill=(255, 255, 255), 
                 stroke_width=2, stroke_fill=(0, 0, 0))
        
        # Add title (wrapped) - much larger
        y_pos = 160
        wrapped_title = textwrap.wrap(title, width=18)
        for line in wrapped_title[:2]:  # Max 2 lines
            draw.text((50, y_pos), line, font=title_font, fill=(255, 255, 255), 
                     stroke_width=3, stroke_fill=(0, 0, 0))
            y_pos += 100
        
        # Add studio info with larger font
        studio = anime_data.get('studios', {}).get('nodes', [{}])[0].get('name', 'Unknown Studio')
        draw.text((50, y_pos + 40), f"🎬 {studio}", font=info_font, fill=(255, 255, 255))
        
        # Add genres with larger font
        genres = ', '.join(anime_data.get('genres', [])[:3])
        draw.text((50, y_pos + 95), f"🎭 {genres}", font=info_font, fill=(255, 255, 255))
        
        # Add season and episodes info
        season = anime_data.get('season', '').capitalize() if anime_data.get('season') else 'Unknown'
        year = anime_data.get('seasonYear', '')
        episodes = anime_data.get('episodes', '?')
        
        season_text = f"{season} {year}" if year else season
        episode_text = f"{episodes} Episodes" if episodes != '?' else "Episodes TBA"
        
        draw.text((50, y_pos + 150), f"📅 {season_text} • {episode_text}", 
                 font=info_font, fill=(255, 255, 255))
        
        # Add score if available
        if anime_data.get('averageScore'):
            draw.text((50, y_pos + 205), f"⭐ Score: {anime_data['averageScore']}/100", 
                     font=info_font, fill=(255, 255, 255))
        
        # Add vertical "ANIME MAYHEM" text on the right side
        # Create text image for rotation
        sidebar_text = "ANIME MAYHEM"
        
        # Calculate text size for proper positioning
        bbox = draw.textbbox((0, 0), sidebar_text, font=logo_font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Create temporary image for text
        text_img = Image.new('RGBA', (text_width + 20, text_height + 20), (0, 0, 0, 0))
        text_draw = ImageDraw.Draw(text_img)
        text_draw.text((10, 10), sidebar_text, font=logo_font, fill=(255, 255, 255), 
                      stroke_width=2, stroke_fill=(0, 0, 0))
        
        # Rotate 90 degrees
        text_img = text_img.rotate(90, expand=True)
        
        # Paste on main image
        text_x = self.width - 60
        text_y = self.height // 2 - text_img.height // 2
        poster.paste(text_img, (text_x, text_y), text_img)
        
        return poster

    def generate_manhwa_banner(self, media_data):
        """Generate a 1280x500 manhwa banner based on the provided design"""
        width, height = 1280, 500
        banner = Image.new('RGBA', (width, height), (0, 0, 0, 255))
        draw = ImageDraw.Draw(banner)

        # 1. Background Image (Right Side)
        if media_data.get('bannerImage') or media_data.get('coverImage', {}).get('extraLarge'):
            img_url = media_data.get('bannerImage') or media_data['coverImage']['extraLarge']
            right_img = self.download_image(img_url).convert('RGBA')

            # Resize and crop to fill the right 45%
            target_width = int(width * 0.45)
            aspect = right_img.width / right_img.height
            new_height = height
            new_width = int(new_height * aspect)
            if new_width < target_width:
                new_width = target_width
                new_height = int(new_width / aspect)

            right_img = right_img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Center crop
            left = (new_width - target_width) // 2
            top = (new_height - height) // 2
            right_img = right_img.crop((left, top, left + target_width, top + height))

            banner.paste(right_img, (width - target_width, 0))

        # 2. Dark Fade Overlay on the right image
        # Simulated radial-gradient(circle at center, transparent 40%, black 90%)
        overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        target_width = int(width * 0.45)
        center_x = width - target_width // 2
        center_y = height // 2
        # We need a large enough radius to cover the right side
        radius = int(target_width * 0.8)

        # Radial gradient from transparent to black
        for r_curr in range(radius, 0, -1):
            f = r_curr / radius
            # 0.4 to 0.9 range from the CSS
            if f < 0.4:
                alpha = 0
            elif f > 0.9:
                alpha = 255
            else:
                alpha = int(255 * (f - 0.4) / (0.9 - 0.4))

            overlay_draw = ImageDraw.Draw(overlay)
            overlay_draw.ellipse([center_x-r_curr, center_y-r_curr, center_x+r_curr, center_y+r_curr],
                               fill=(0, 0, 0, alpha))

        # Fill outside the radial gradient on the right
        banner = Image.alpha_composite(banner, overlay)
        draw = ImageDraw.Draw(banner)

        # 3. Decorative Circles on the right side
        # Top circle
        self.draw_radial_gradient(banner, (width - 220, 55), 35, (79, 223, 255, 204), (0, 94, 255, 204))
        # Bottom circle
        self.draw_radial_gradient(banner, (width - 480, height - 60), 40, (79, 223, 255, 204), (0, 94, 255, 204))

        # 4. Top & Bottom Border Glow
        # linear-gradient(to right, transparent, #00eaff, transparent)
        cyan_glow = (0, 234, 255, 255)
        transparent = (0, 234, 255, 0)

        top_glow = Image.new('RGBA', (width, 2), (0, 0, 0, 0))
        top_draw = ImageDraw.Draw(top_glow)
        self.draw_linear_gradient(top_draw, (0, 0, width//2, 2), transparent, cyan_glow)
        self.draw_linear_gradient(top_draw, (width//2, 0, width, 2), cyan_glow, transparent)
        banner.paste(top_glow, (0, 0), top_glow)
        banner.paste(top_glow, (0, height - 2), top_glow)

        # 5. Side Border Lines
        # linear-gradient(to bottom, transparent, #00eaff, transparent)
        side_glow = Image.new('RGBA', (2, height), (0, 0, 0, 0))
        side_draw = ImageDraw.Draw(side_glow)
        self.draw_linear_gradient(side_draw, (0, 0, 2, height//2), transparent, cyan_glow, horizontal=False)
        self.draw_linear_gradient(side_draw, (0, height//2, 2, height), cyan_glow, transparent, horizontal=False)
        banner.paste(side_glow, (0, 0), side_glow)
        banner.paste(side_glow, (width - 2, 0), side_glow)

        # 6. Vertical Neon Line (Left)
        def draw_vert_line(draw, color):
            draw.rectangle([25, 50, 29, height - 50], fill=color)

        # Glow for the line
        self.draw_glow_shape(banner, draw_vert_line, (0, 234, 255, 255), (0, 234, 255, 150), 10)

        # 7. Left Content - Text
        title_font = self._get_font('bold', 60)
        small_font = self._get_font('regular', 13)
        tag_font = self._get_font('bold', 18)
        desc_font = self._get_font('regular', 13)
        button_font = self._get_font('bold', 14)

        # Small Title
        draw.text((50, 60), "MANHWA SORROWS", font=small_font, fill=(207, 207, 207))

        # Main Title
        title = media_data['title'].get('english') or media_data['title']['romaji']
        y_pos = 85
        wrapped_title = textwrap.wrap(title.upper(), width=20)
        for line in wrapped_title[:2]:
            draw.text((50, y_pos), line, font=title_font, fill=(255, 255, 255))
            y_pos += 65

        # Divider 1
        div_y = y_pos + 10
        div_width = int(width * 0.85 * 0.55) # 85% of left side
        self.draw_linear_gradient(draw, (50, div_y, 50 + div_width, div_y + 2), (0, 234, 255, 255), (0, 234, 255, 0))

        # Tags
        y_pos = div_y + 15
        tags = [g.upper() for g in media_data.get('genres', [])[:3]]
        tag_x = 50
        for tag in tags:
            draw.text((tag_x, y_pos), tag, font=tag_font, fill=(255, 255, 255))
            tag_x += 160

        # Divider 2
        y_pos += 35
        self.draw_linear_gradient(draw, (50, y_pos, 50 + div_width, y_pos + 2), (0, 234, 255, 255), (0, 234, 255, 0))

        # Description
        y_pos += 15
        desc = self.clean_html(media_data.get('description', 'No description available.'))
        wrapped_desc = textwrap.wrap(desc, width=80)
        for line in wrapped_desc[:5]:
            draw.text((50, y_pos), line, font=desc_font, fill=(191, 191, 191))
            y_pos += 22

        # Buttons (Static)
        y_pos += 25
        # Join Now Button (White)
        draw.rectangle([50, y_pos, 160, y_pos + 40], fill=(255, 255, 255))
        draw.text((65, y_pos + 10), "JOIN NOW", font=button_font, fill=(0, 0, 0))

        # Manhwa Sorrows Button (Dark)
        draw.rectangle([170, y_pos, 350, y_pos + 40], fill=(17, 17, 17), outline=(68, 68, 68), width=1)
        draw.text((185, y_pos + 10), "MANHWA SORROWS", font=button_font, fill=(255, 255, 255))

        return banner.convert('RGB')

# Bot handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    welcome_text = """
🎬 Welcome to Anime Mayhem Bot! 🎬

I can create stunning anime posters and manhwa banners for you!

📝 How to use:
• Send an anime name to get a poster.
• Use /manhwa <name> to get a manhwa banner.

Example: "One Piece" or "/manhwa Solo Leveling"

Let's create some amazing posters! 🎨
    """
    await update.message.reply_text(welcome_text)

async def handle_manhwa_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle manhwa search and banner generation"""
    query = ' '.join(context.args)
    if not query:
        await update.message.reply_text("Please provide a manhwa name. Example: /manhwa Solo Leveling")
        return

    # Send processing message
    processing_msg = await update.message.reply_text("🔍 Searching for manhwa and generating banner...")

    try:
        # Search manhwa
        generator = AnimePosterGenerator()
        media_data = generator.search_media(query, "MANGA")

        if not media_data:
            await processing_msg.edit_text("❌ Manhwa not found. Please try another name.")
            return

        # Update status
        await processing_msg.edit_text("🎨 Creating your banner...")

        # Generate banner
        banner = generator.generate_manhwa_banner(media_data)

        # Save to buffer
        buffer = BytesIO()
        banner.save(buffer, format='PNG', quality=95)
        buffer.seek(0)

        # Send banner
        title = media_data['title'].get('english') or media_data['title']['romaji']
        caption = f"🎬 {title}\n\nGenerated by Anime Mayhem Bot"

        await update.message.reply_photo(
            photo=buffer,
            caption=caption
        )

        # Delete processing message
        await processing_msg.delete()

    except Exception as e:
        await processing_msg.edit_text(f"❌ Error generating banner: {str(e)}")

async def handle_anime_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle anime search and poster generation"""
    query = update.message.text
    
    # Send processing message
    processing_msg = await update.message.reply_text("🔍 Searching for anime and generating poster...")
    
    try:
        # Search anime
        generator = AnimePosterGenerator()
        anime_data = generator.search_media(query, "ANIME")
        
        if not anime_data:
            await processing_msg.edit_text("❌ Anime not found. Please try another name.")
            return
        
        # Update status
        await processing_msg.edit_text("🎨 Creating your poster...")
        
        # Generate poster
        poster = generator.generate_poster(anime_data)
        
        # Save to buffer
        buffer = BytesIO()
        poster.save(buffer, format='PNG', quality=95)
        buffer.seek(0)
        
        # Send poster
        title = anime_data['title'].get('english') or anime_data['title']['romaji']
        caption = f"🎬 {title}\n\nGenerated by Anime Mayhem Bot"
        
        await update.message.reply_photo(
            photo=buffer,
            caption=caption
        )
        
        # Delete processing message
        await processing_msg.delete()
        
    except Exception as e:
        await processing_msg.edit_text(f"❌ Error generating poster: {str(e)}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command handler"""
    help_text = """
🎬 Anime Mayhem Bot Help

Commands:
/start - Start the bot
/help - Show this help message
/manhwa <name> - Generate a manhwa banner

Usage:
• Simply send any anime name to generate a poster!
• Use /manhwa followed by the name to generate a banner!

Examples:
• One Piece
• /manhwa Solo Leveling
• Demon Slayer
• /manhwa The Stellar Swordmaster

The bot will search AniList and create a custom design for you! 🎨
    """
    await update.message.reply_text(help_text)

def main():
    """Start the bot"""
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("manhwa", handle_manhwa_search))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_anime_search))
    
    # Start bot
    print("🤖 Anime Mayhem Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
