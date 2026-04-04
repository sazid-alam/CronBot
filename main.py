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
    return "Sous-Chef is active and the kitchen is open! 👨‍🍳"

def run_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_server, daemon=True)
    t.start()

# --- 2. INTERACTIVE COMPONENTS ---
class RegisterView(discord.ui.View):
    """Adds a clickable button to the message"""
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
        
        # Platform Branding Map (Colors and Logos)
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
        print(f"✅ {self.user.name} is online on Railway with Gourmet features!")

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
        # 1. Branding & Logic
        if is_reminder and len(contests) == 1:
            # Single contest reminder gets full branding
            c = contests[0]
            brand = self.branding.get(c['resource_id'], {"color": 0xe74c3c, "logo": None, "icon": "⭐"})
            title = f"⚠️ CONTEST ALERT: {brand['name']}"
            color = brand['color']
        else:
            # Multi-contest list gets a general theme
            title = "🚀 Upcoming CP Contests (DU_Rumbling)"
            color = 0x3498db
            brand = {"logo": None}

        embed = discord.Embed(title=title, color=color, timestamp=datetime.now(UTC))
        
        if brand["logo"]:
            embed.set_thumbnail(url=brand["logo"])
        
        if not contests:
            embed.description = "The kitchen is empty! No quality rounds found."
            return embed

        for c in contests[:(1 if is_reminder else 10)]:
            try:
                # 2. BST Time Calculation (UTC + 6)
                start_dt_utc = datetime.fromisoformat(c['start'].replace('Z', '')).replace(tzinfo=UTC)
                start_dt_bst = start_dt_utc + timedelta(hours=6)
                
                bst_str = start_dt_bst.strftime("%I:%M %p, %d %b") # e.g. 08:00 PM, 05 Apr
                rel_ts = f"<t:{int(start_dt_utc.timestamp())}:R>"
                
                brand_info = self.branding.get(c['resource_id'], {"icon": "⭐"})
                
                embed.add_field(
                    name=f"{brand_info['icon']} {c['event']}",
                    value=f"📅 **BST:** `{bst_str}`\n⏳ **Starts:** {rel_ts}\n[Register Here]({c['href']})",
                    inline=False
                )
            except: continue
        
        embed.set_footer(text="Times shown in Bangladesh Standard Time (BST)")
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
                # Create the interactive button
                view = RegisterView(c['href'])
                
                await channel.send(
                    content="🔔 **Heads up! A high-quality round starts in 30 minutes!**", 
                    embed=embed, 
                    view=view
                )
                self.sent_reminders.add(c['id'])

bot = SousChef()

# --- 4. SLASH COMMANDS ---
@bot.tree.command(name="ping", description="Check the kitchen's response time")
async def ping_slash(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Pong! `{round(bot.latency * 1000)}ms`")

@bot.tree.command(name="contests", description="Show upcoming high-quality CP contests in BST")
async def contests_slash(interaction: discord.Interaction):
    await interaction.response.defer()
    data = await bot.fetch_contests()
    embed = bot.create_embed(data)
    await interaction.followup.send(embed=embed)

# --- 5. EXECUTION ---
if __name__ == "__main__":
    if not TOKEN:
        print("❌ ERROR: DISCORD_TOKEN is missing!")
    else:
        keep_alive()
        bot.run(TOKEN)
