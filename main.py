import os
import discord
import aiohttp
import asyncio
from flask import Flask
from threading import Thread
from discord import app_commands  # NEW: For Slash Commands
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

# --- 2. CONFIGURATION ---
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
        # Prefix is still "!" for backup, but focus is Slash Commands
        super().__init__(command_prefix="!", intents=intents, help_command=None)
        self.sent_reminders = set()

    async def setup_hook(self):
        # 1. Start the background patrol
        self.reminder_patrol.start()
        
        # 2. Sync Slash Commands to Discord
        print("🔄 Syncing slash commands...")
        try:
            synced = await self.tree.sync()
            print(f"✅ Synced {len(synced)} slash commands!")
        except Exception as e:
            print(f"❌ Failed to sync commands: {e}")

    async def on_ready(self):
        print(f"---")
        print(f"✅ SUCCESS: {self.user.name} is online and Slash-ready!")
        print(f"📡 Monitoring Channel: {CHANNEL_ID}")
        print(f"---")

    # --- API LOGIC (Unchanged) ---
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
        title = "⚠️ UPCOMING CONTEST ALERT" if is_reminder else "🚀 Upcoming CP Contests"
        color = 0xe74c3c if is_reminder else 0x3498db
        embed = discord.Embed(title=title, color=color, timestamp=datetime.now(UTC))
        if not contests:
            embed.description = "No quality rounds found."
            return embed
        for c in contests[:(1 if is_reminder else 10)]:
            try:
                start_dt = datetime.fromisoformat(c['start'].replace('Z', '')).replace(tzinfo=UTC)
                ts = f"<t:{int(start_dt.timestamp())}:R>"
                embed.add_field(name=f"⭐ {c['event']}", value=f"Starts: {ts}\n[Link]({c['href']})", inline=False)
            except: continue
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
                await channel.send(content="🔔 **Round starting in 30 minutes!**", embed=embed)
                self.sent_reminders.add(c['id'])

bot = SousChef()

# --- 3. SLASH COMMANDS SECTION ---

@bot.tree.command(name="ping", description="Check the kitchen's response time")
async def ping_slash(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Pong! `{round(bot.latency * 1000)}ms`")

@bot.tree.command(name="contests", description="Show upcoming high-quality CP contests")
async def contests_slash(interaction: discord.Interaction):
    # API calls take time. We "defer" to show "Sous-Chef is thinking..."
    await interaction.response.defer()
    
    data = await bot.fetch_contests()
    embed = bot.create_embed(data)
    
    # Use followup.send after deferring
    await interaction.followup.send(embed=embed)

# --- 4. EXECUTION ---
if __name__ == "__main__":
    if not TOKEN:
        print("❌ ERROR: DISCORD_TOKEN is missing!")
    else:
        keep_alive()
        bot.run(TOKEN)
