import os
import discord
import aiohttp
import asyncio
from flask import Flask
from threading import Thread
from discord.ext import tasks, commands
from datetime import datetime, UTC, timedelta

# --- 1. HEALTH CHECK SERVER ---
# Railway will use this to confirm your app is "Healthy"
app = Flask('')

@app.route('/')
def home():
    return "Sous-Chef is active and the kitchen is open! 👨‍🍳"

def run_server():
    # Railway provides the PORT environment variable automatically
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

RESOURCES = "1,2,93"  # Codeforces, CodeChef, AtCoder

class SousChef(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents, help_command=None)
        self.sent_reminders = set()

    async def setup_hook(self):
        print("🔧 Initializing background tasks...")
        self.reminder_patrol.start()

    async def on_ready(self):
        print(f"---")
        print(f"✅ SUCCESS: {self.user.name} is online on Railway!")
        print(f"📡 Monitoring Channel: {CHANNEL_ID}")
        print(f"---")

    async def fetch_contests(self):
        now = datetime.now(UTC) - timedelta(hours=2)
        formatted_date = now.strftime('%Y-%m-%dT%H:%M:%S')
        
        url = (f"https://clist.by/api/v2/contest/?"
               f"username={CLIST_USER}&api_key={CLIST_KEY}&"
               f"resource_id__in={RESOURCES}&start__gte={formatted_date}&"
               f"order_by=start&format=json&limit=50")
        
        async with aiohttp.ClientSession(headers={"Accept": "application/json"}) as session:
            try:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return self.filter_menu(data.get('objects', []))
                    print(f"⚠️ CLIST API Error: {resp.status}")
                    return []
            except Exception as e:
                print(f"⚠️ Fetch Error: {e}")
                return []

    def filter_menu(self, contests):
        filtered = []
        for c in contests:
            name = c['event'].lower()
            res_id = c['resource_id']
            if res_id == 1: # CF
                if any(k in name for k in ["div. 2", "div. 3", "div. 4", "div. 1 + 2", "educational"]):
                    filtered.append(c)
            elif res_id == 2: # CC
                if "starters" in name:
                    filtered.append(c)
            elif res_id == 93: # AtCoder
                if "beginner" in name:
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
                embed.add_field(
                    name=f"⭐ {c['event']}",
                    value=f"**Platform:** {c['resource']}\n**Starts:** {ts}\n[Link]({c['href']})",
                    inline=False
                )
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
                await channel.send(content="🔔 **Get ready! Contest starts in 30 minutes!**", embed=embed)
                self.sent_reminders.add(c['id'])

bot = SousChef()

@bot.command(name="contests", aliases=["contest"])
async def contests_command(ctx):
    async with ctx.typing():
        data = await bot.fetch_contests()
        await ctx.send(embed=bot.create_embed(data))

@bot.command(name="ping")
async def ping(ctx):
    await ctx.send(f"🏓 Pong! `{round(bot.latency * 1000)}ms`")

# --- 3. EXECUTION ---
if __name__ == "__main__":
    if not TOKEN:
        print("❌ ERROR: DISCORD_TOKEN is missing!")
    else:
        keep_alive()
        bot.run(TOKEN)
