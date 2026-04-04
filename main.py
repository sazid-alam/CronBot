import os
import json
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
        
        self.memory_file = "sent_reminders.json"
        self.sent_reminders = self.load_memory()
        
        # NOTE: Repo must be PUBLIC for these logos to show in Discord
        img_base = "https://raw.githubusercontent.com/sazid-alam/SousChefBot/main"
        self.branding = {
            1:  {"name": "Codeforces", "color": 0x318ce7, "icon": "🟦", "logo": f"{img_base}/cf.png"},
            2:  {"name": "CodeChef",   "color": 0x5b2d22, "icon": "🟫", "logo": f"{img_base}/cc.png"},
            93: {"name": "AtCoder",    "color": 0x222222, "icon": "⬛", "logo": f"{img_base}/ac.png"}
        }

    def load_memory(self):
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, "r") as f:
                    return set(json.load(f))
            except: pass
        return set()

    def save_memory(self):
        with open(self.memory_file, "w") as f:
            json.dump(list(self.sent_reminders), f)

    async def setup_hook(self):
        self.reminder_patrol.start()
        print("🔄 Syncing slash commands...")
        await self.tree.sync()

    async def on_ready(self):
        print(f"✅ {self.user.name} is online. @everyone pings active.")

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
                        return data.get('objects', [])
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
        if is_reminder and len(contests) == 1:
            c = contests[0]
            brand = self.branding.get(c['resource_id'], {"color": 0x2b2d31, "logo": None})
            ts = int(datetime.fromisoformat(c['start'].replace('Z', '')).replace(tzinfo=UTC).timestamp())
            
            embed = discord.Embed(
                title=f"◈ {c['event']}", 
                description=f"<t:{ts}:F>\n┕ <t:{ts}:R>",
                color=brand['color']
            )
            if brand["logo"]:
                embed.set_thumbnail(url=brand["logo"])
            return embed

        embed = discord.Embed(title="Upcoming Contests", color=0x2b2d31)
        filtered = self.filter_menu(contests)
        if not filtered:
            embed.description = "*No quality rounds scheduled.*"
            return embed

        lines = []
        for c in filtered[:10]:
            try:
                ts = int(datetime.fromisoformat(c['start'].replace('Z', '')).replace(tzinfo=UTC).timestamp())
                brand_info = self.branding.get(c['resource_id'], {"icon": "•"})
                lines.append(f"{brand_info['icon']} **[{c['event']}]({c['href']})**\n┕ <t:{ts}:f> (<t:{ts}:R>)\n")
            except: continue
        
        embed.description = "\n".join(lines)
        embed.set_footer(text="DU_Rumbling • Auto-localized")
        return embed

    @tasks.loop(minutes=1)
    async def reminder_patrol(self):
        await self.wait_until_ready()
        channel = self.get_channel(CHANNEL_ID)
        if not channel: return
        
        all_objects = await self.fetch_contests()
        filtered_contests = self.filter_menu(all_objects)
        now = datetime.now(UTC)
        
        # 1. Cleanup Memory
        active_ids = {str(c['id']) for c in all_objects}
        self.sent_reminders = {rid for rid in self.sent_reminders if rid in active_ids}
        
        # 2. Check for Reminders (20-30 min window)
        for c in filtered_contests:
            start_dt = datetime.fromisoformat(c['start'].replace('Z', '')).replace(tzinfo=UTC)
            diff = (start_dt - now).total_seconds() / 60
            
            if 20 <= diff <= 30 and str(c['id']) not in self.sent_reminders:
                embed = self.create_embed([c], is_reminder=True)
                view = RegisterView(c['href'])
                
                # --- MODIFIED LINE BELOW ---
                await channel.send(content="@everyone 🔔 **30-minute alert!**", embed=embed, view=view)
                
                self.sent_reminders.add(str(c['id']))
        
        self.save_memory()

bot = SousChef()

@bot.tree.command(name="ping", description="Check latency")
async def ping_slash(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 `{round(bot.latency * 1000)}ms`", ephemeral=True)

@bot.tree.command(name="contests", description="Show upcoming CP contests")
async def contests_slash(interaction: discord.Interaction):
    await interaction.response.defer()
    data = await bot.fetch_contests()
    embed = bot.create_embed(data)
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="test_reminder", description="Preview reminder visuals")
async def test_reminder(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    data = await bot.fetch_contests()
    filtered = bot.filter_menu(data)
    if filtered:
        embed = bot.create_embed([filtered[0]], is_reminder=True)
        view = RegisterView(filtered[0]['href'])
        await interaction.followup.send(content="@everyone 🧪 **Test Preview:**", embed=embed, view=view)
    else:
        await interaction.followup.send("No contests found to test.")

if __name__ == "__main__":
    if TOKEN:
        keep_alive()
        bot.run(TOKEN)
