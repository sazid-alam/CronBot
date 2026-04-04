import os
import discord
import aiohttp
from discord.ext import tasks, commands
from dotenv import load_dotenv
from datetime import datetime, UTC, timedelta

# 1. SETUP
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
CLIST_USER = os.getenv('CLIST_USERNAME')
CLIST_KEY = os.getenv('CLIST_API_KEY')
CHANNEL_ID = int(os.getenv('CHANNEL_ID'))
RESOURCES = "1,2,93" 

class SousChef(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        super().__init__(command_prefix="!", intents=intents, help_command=None)
        
        self.sent_reminders = set()

    async def setup_hook(self):
        self.reminder_patrol.start()

    async def fetch_contests(self):
        """Fetches and filters only the specific rounds you want."""
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
                        all_contests = data.get('objects', [])
                        return self.filter_menu(all_contests)
                    return []
            except Exception as e:
                print(f"Connection Error: {e}")
                return []

    def filter_menu(self, contests):
        """The 'Sieve': Only keeps rounds matching your specific list."""
        filtered = []
        for c in contests:
            name = c['event'].lower()
            res_id = c['resource_id']

            # Codeforces (ID: 1)
            if res_id == 1:
                cf_keywords = ["div. 2", "div. 3", "div. 4", "div. 1 + 2", "educational"]
                if any(k in name for k in cf_keywords):
                    filtered.append(c)
            
            # CodeChef (ID: 2)
            elif res_id == 2:
                if "starters" in name:
                    filtered.append(c)
            
            # AtCoder (ID: 93)
            elif res_id == 93:
                if "beginner" in name:
                    filtered.append(c)
                    
        return filtered

    def create_embed(self, contests, is_reminder=False):
        title = "⚠️ UPCOMING CONTEST ALERT" if is_reminder else "🚀 Upcoming CP Contests"
        color = 0xe74c3c if is_reminder else 0x3498db
        
        embed = discord.Embed(title=title, color=color, timestamp=datetime.now(UTC))
        
        if not contests:
            embed.description = "The kitchen is empty! No filtered rounds found."
            return embed

        # Show top 10 for manual list, 1 for patrol reminder
        display_limit = 1 if is_reminder else 10
        
        for c in contests[:display_limit]:
            try:
                start_str = c['start'].replace('Z', '')
                start_dt = datetime.fromisoformat(start_str).replace(tzinfo=UTC)
                ts = f"<t:{int(start_dt.timestamp())}:R>"
                
                embed.add_field(
                    name=f"⭐ {c['event']}",
                    value=f"**Platform:** {c['resource']}\n**Starts:** {ts}\n[Register Here]({c['href']})",
                    inline=False
                )
            except: continue
            
        embed.set_footer(text="👨‍🍳 Sous-Chef | Quality Rounds Only")
        return embed

    @tasks.loop(minutes=1)
    async def reminder_patrol(self):
        """Patrols every minute for contests starting in 20-30 minutes."""
        await self.wait_until_ready()
        channel = self.get_channel(CHANNEL_ID)
        if not channel: return

        contests = await self.fetch_contests()
        now = datetime.now(UTC)

        for c in contests:
            contest_id = c['id']
            start_str = c['start'].replace('Z', '')
            start_dt = datetime.fromisoformat(start_str).replace(tzinfo=UTC)
            diff = (start_dt - now).total_seconds() / 60

            # Proactive Reminder Trigger
            if 20 <= diff <= 30 and contest_id not in self.sent_reminders:
                embed = self.create_embed([c], is_reminder=True)
                await channel.send(content="🔔 **Heads up! Your round starts in 30 minutes!**", embed=embed)
                self.sent_reminders.add(contest_id)
                print(f"🚨 Reminder sent for: {c['event']}")

# 2. INITIALIZATION
bot = SousChef()

@bot.event
async def on_ready():
    print(f"👨‍🍳 {bot.user.name} is online and filtering the menu!")

@bot.command(name="contests", aliases=["contest"])
async def contests_command(ctx):
    async with ctx.typing():
        data = await bot.fetch_contests()
        embed = bot.create_embed(data)
        await ctx.send(embed=embed)

@bot.command(name="ping")
async def ping(ctx):
    await ctx.send(f"🏓 Pong! `{round(bot.latency * 1000)}ms`")

if __name__ == "__main__":
    bot.run(TOKEN)