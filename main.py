import os
import discord
import aiohttp
import asyncio
from flask import Flask
from threading import Thread
from discord import app_commands
from discord.ext import tasks, commands
from datetime import datetime, UTC, timedelta

# --- 1. HEALTH CHECK SERVER ---
app = Flask('')

@app.route('/')
def home():
    return "Sous-Chef is active! 👨‍🍳"

def run_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_server, daemon=True)
    t.start()

# --- 2. INTERACTIVE COMPONENTS ---
class RegisterView(discord.ui.View):
    def __init__(self, url):
        super().__init__()
        self.add_item(discord.ui.Button(label="Register on Platform", url=url, style=discord.ButtonStyle.link))

# --- 3. THE BOT CLASS ---
TOKEN = os.environ.get('DISCORD_TOKEN')
CLIST_USER = os.environ.get('CLIST_USERNAME')
CLIST_KEY = os.environ.get('CLIST_API_KEY')
CHANNEL_ID_STR = os.environ.get('CHANNEL_ID', '0')

try:
    CHANNEL_ID = int(CHANNEL_ID_STR)
except ValueError:
    CHANNEL_ID = 0

RESOURCES = "1,2,93" 

class SousChef(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents, help_command=None)
        self.sent_reminders = set()
        
        # Platform Branding (Muted colors for a classier look)
        self.branding = {
            1:  {"name": "Codeforces", "color": 0x318ce7, "icon": "🟦", "logo": "https://i.imgur.com/89SclG0.png"},
            2:  {"name": "CodeChef",   "color": 0x5b2d22, "icon": "🟫", "logo": "https://i.imgur.com/9n07R9S.png"},
            93: {"name": "AtCoder",    "color": 0x222222, "icon": "⬛", "logo": "https://i.imgur.com/6NOn0A4.png"}
        }

    async def setup_hook(self):
        self.reminder_patrol.start()
        print("🔄 Syncing slash commands...")
        await self.tree.sync()

    async def on_ready(self):
        print(f"✅ {self.user.name} is online and minimal.")

    async def fetch_contests(self):
        now = (datetime.now(UTC) - timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M:%S')
        url = (f"https://clist.by/api/v2/contest/?"
               f"username={CLIST_USER}&api_key={CLIST_KEY}&"
               f"resource_id__in={RESOURCES}&start__gte={now}&"
               f"order_by=start&format=json&limit=50")
        
        async with aiohttp.ClientSession(headers={"Accept": "application/json"}) as session:
            try:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return self.filter_menu(data.get('objects', []))
                    return []
            except: return []

    def filter_menu(self, contests):
        filtered = []
        for c in contests:
            name = c['event'].lower()
            res_id = c['resource_id']
            if res_id == 1 and any(k in name for k in ["div. 2", "div. 3", "div. 4", "div. 1 + 2", "educational"]):
                filtered.append(c)
            elif res_id == 2 and "starters" in name:
                filtered.append(c)
            elif res_id == 93 and "beginner" in name:
                filtered.append(c)
        return filtered

    def create_embed(self, contests, is_reminder=False):
        # Use a neutral, classy dark grey (Discord's background color) for lists
        embed_color = 0x2b2d31 

        if is_reminder and len(contests) == 1:
            # Single reminders get a bit more personality
            c = contests[0]
            brand = self.branding.get(c['resource_id'], {"color": 0x2b2d31, "logo": None, "icon": "◈"})
            embed = discord.Embed(
                title=f"{brand['icon']} {c['event']}", 
                description="*A high-quality round is starting soon.*",
                color=brand['color']
            )
            if brand["logo"]:
                embed.set_thumbnail(url=brand["logo"])
            
            ts = int(datetime.fromisoformat(c['start'].replace('Z', '')).replace(tzinfo=UTC).timestamp())
            embed.add_field(name="Schedule", value=f"<t:{ts}:F>\n┕ <t:{ts}:R>")
            return embed

        # --- Minimalist List View ---
        embed = discord.Embed(title="Upcoming Contests", color=embed_color)
        
        if not contests:
            embed.description = "*The kitchen is empty.*"
            return embed

        description_lines = []
        for c in contests[:10]:
            try:
                # Get the Unix timestamp (UTC)
                ts = int(datetime.fromisoformat(c['start'].replace('Z', '')).replace(tzinfo=UTC).timestamp())
                brand_info = self.branding.get(c['resource_id'], {"icon": "•"})
                
                # Single-line elegant format
                # • [Platform Icon] [Title](Link)
                # ┕ [Full Date/Time] ([Relative Time])
                line = (f"{brand_info['icon']} **[{c['event']}]({c['href']})**\n"
                        f"┕ <t:{ts}:f> (<t:{ts}:R>)\n")
                description_lines.append(line)
            except: continue

        embed.description = "\n".join(description_lines)
        embed.set_footer(text="DU_Rumbling • Auto-localized time")
        return embed

    @tasks.loop(minutes=1)
    async def reminder_patrol(self):
        await self.wait_until_ready()
        channel = self.get_channel(CHANNEL_ID)
        if not channel: return
        
        contests = await self.fetch_contests()
        now = datetime.now(UTC)
        
        for c in contests:
            start_dt = datetime.fromisoformat(c['start'].replace('Z', '')).replace(tzinfo=UTC)
            diff = (start_dt - now).total_seconds() / 60
            
            if 20 <= diff <= 30 and c['id'] not in self.sent_reminders:
                embed = self.create_embed([c], is_reminder=True)
                view = RegisterView(c['href'])
                
                await channel.send(
                    content="🔔 **30-minute round alert!**", 
                    embed=embed, 
                    view=view
                )
                self.sent_reminders.add(c['id'])

bot = SousChef()

# --- 4. SLASH COMMANDS ---
@bot.tree.command(name="ping", description="Check latency")
async def ping_slash(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 `{round(bot.latency * 1000)}ms`", ephemeral=True)

@bot.tree.command(name="contests", description="Show upcoming CP contests")
async def contests_slash(interaction: discord.Interaction):
    await interaction.response.defer()
    data = await bot.fetch_contests()
    embed = bot.create_embed(data)
    await interaction.followup.send(embed=embed)

# --- 5. EXECUTION ---
if __name__ == "__main__":
    if TOKEN:
        keep_alive()
        bot.run(TOKEN)
