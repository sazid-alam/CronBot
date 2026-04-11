import os
import sys
import aiosqlite
import logging
import discord
import aiohttp
import asyncio
from discord import app_commands
from discord.ext import tasks, commands
from datetime import datetime, UTC, timedelta, time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("CronBot")

# --- 1. SETUP & VALIDATION ---
TOKEN = os.environ.get('DISCORD_TOKEN')
CLIST_USER = os.environ.get('CLIST_USERNAME')
CLIST_KEY = os.environ.get('CLIST_API_KEY')
if not TOKEN or not CLIST_USER or not CLIST_KEY:
    logger.error("Missing critical environment variables: DISCORD_TOKEN, CLIST_USERNAME, or CLIST_API_KEY.")
    sys.exit(1)

CHANNEL_ID_STR = os.environ.get('CHANNEL_ID', '0')
try:
    CHANNEL_ID = int(CHANNEL_ID_STR)
except ValueError:
    CHANNEL_ID = 0

RESOURCES = "1,2,93"

# --- 2. INTERACTIVE COMPONENTS ---
class RegisterView(discord.ui.View):
    def __init__(self, url):
        super().__init__()
        self.add_item(discord.ui.Button(label="Register on Platform", url=url, style=discord.ButtonStyle.link))

class RoleToggleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        
    async def fetch_ping_role(self, interaction: discord.Interaction):
        async with aiosqlite.connect(interaction.client.db_file) as db:
            async with db.execute("SELECT role_id FROM guild_config WHERE guild_id = ?", (str(interaction.guild_id),)) as cursor:
                row = await cursor.fetchone()
        
        if not row or not row[0]:
            if not interaction.response.is_done():
                await interaction.response.send_message("The server admin hasn't configured a ping role yet.", ephemeral=True)
            return None
            
        role = interaction.guild.get_role(int(row[0]))
        if not role:
            if not interaction.response.is_done():
                await interaction.response.send_message("The configured ping role no longer exists.", ephemeral=True)
            return None
        return role

    @discord.ui.button(label="Get Role", style=discord.ButtonStyle.success, custom_id="persistent_role_get", emoji="✅")
    async def get_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = await self.fetch_ping_role(interaction)
        if not role: return
        
        if role in interaction.user.roles:
            await interaction.response.send_message(f"You already have the **{role.name}** role!", ephemeral=True)
        else:
            try:
                await interaction.user.add_roles(role)
                await interaction.response.send_message(f"✅ Given the **{role.name}** role! You will now be mentioned for contests.", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message("I don't have permission to manage this role. Make sure the bot's role is higher than the ping role in settings.", ephemeral=True)
            except Exception as e:
                logger.warning(f"Error giving role: {e}")

    @discord.ui.button(label="Remove Role", style=discord.ButtonStyle.danger, custom_id="persistent_role_remove", emoji="❌")
    async def remove_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = await self.fetch_ping_role(interaction)
        if not role: return
        
        if role not in interaction.user.roles:
            await interaction.response.send_message(f"You don't have the **{role.name}** role to begin with!", ephemeral=True)
        else:
            try:
                await interaction.user.remove_roles(role)
                await interaction.response.send_message(f"❌ Removed the **{role.name}** role.", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message("I don't have permission to manage this role. Make sure the bot's role is higher than the ping role in settings.", ephemeral=True)
            except Exception as e:
                logger.warning(f"Error removing role: {e}")

    @discord.ui.button(label="Check Status", style=discord.ButtonStyle.secondary, custom_id="persistent_role_status", emoji="🔍")
    async def check_status(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = await self.fetch_ping_role(interaction)
        if not role: return
        
        if role in interaction.user.roles:
            await interaction.response.send_message(f"✅ You **currently have** the **{role.name}** role and will receive notifications.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ You **DO NOT** have the **{role.name}** role.", ephemeral=True)

# --- 3. THE BOT CLASS ---
class ConfigGroup(app_commands.Group):
    def __init__(self, bot):
        super().__init__(name="config", description="Admin configuration commands")
        self.bot = bot

    async def on_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ You need Manage Server permissions to use config commands!", ephemeral=True)
        else:
            logger.error(f"Config command error: {error}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ An error occurred while executing the command.", ephemeral=True)
            except Exception:
                pass

    @app_commands.command(name="set_channel", description="Set the channel for contest announcements")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        async with aiosqlite.connect(self.bot.db_file) as db:
            await db.execute("INSERT INTO guild_config (guild_id, channel_id) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET channel_id=excluded.channel_id", (str(interaction.guild_id), str(channel.id)))
            await db.commit()
        await interaction.response.send_message(f"✅ Alert channel set to {channel.mention}", ephemeral=True)

    @app_commands.command(name="set_ping_role", description="Set the role to ping for contests")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_ping_role(self, interaction: discord.Interaction, role: discord.Role):
        async with aiosqlite.connect(self.bot.db_file) as db:
            await db.execute("INSERT INTO guild_config (guild_id, role_id) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET role_id=excluded.role_id", (str(interaction.guild_id), str(role.id)))
            await db.commit()
        await interaction.response.send_message(f"✅ Ping role set to {role.name}", ephemeral=True)

    @app_commands.command(name="inspect", description="Debug: Verify if SQLite DB data persisted")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def inspect(self, interaction: discord.Interaction):
        async with aiosqlite.connect(self.bot.db_file) as db:
            async with db.execute("SELECT * FROM guild_config WHERE guild_id = ?", (str(interaction.guild_id),)) as cursor:
                data = await cursor.fetchall()
        await interaction.response.send_message(f"📁 **DB State (guild_config):**\n```json\n{data}\n```", ephemeral=True)

    @app_commands.command(name="send_role_menu", description="Send a permanent button menu for users to get the ping role")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def send_role_menu(self, interaction: discord.Interaction):
        async with aiosqlite.connect(self.bot.db_file) as db:
            async with db.execute("SELECT role_id FROM guild_config WHERE guild_id = ?", (str(interaction.guild_id),)) as cursor:
                row = await cursor.fetchone()

        if not row or not row[0]:
            await interaction.response.send_message("Please set a ping role using `/config set_ping_role` first!", ephemeral=True)
            return

        embed = discord.Embed(
            title="🔔 Contest Notifications",
            description="Use the buttons below to manage your contest notifications!\n\n✅ **Get Role** to be notified\n❌ **Remove Role** to stop being notified\n🔍 **Check Status** to verify if you have the role",
            color=0x318ce7
        )
        await interaction.channel.send(embed=embed, view=RoleToggleView())
        await interaction.response.send_message("✅ Role menu sent!", ephemeral=True)

class CronBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(command_prefix="!", intents=intents, help_command=None)
        
        self.db_file = os.environ.get("DB_PATH", "cronbot.db")
        self.sent_reminders = {}
        self.session = None
        
        # NOTE: Repo must be PUBLIC for these logos to show in Discord
        img_base = "https://raw.githubusercontent.com/sazid-alam/CronBot/main"
        self.branding = {
            1:  {"name": "Codeforces", "color": 0x318ce7, "icon": "🟦", "logo": f"{img_base}/cf.png"},
            2:  {"name": "CodeChef",   "color": 0x5b2d22, "icon": "🟫", "logo": f"{img_base}/cc.png"},
            93: {"name": "AtCoder",    "color": 0x222222, "icon": "⬛", "logo": f"{img_base}/ac.png"}
        }

    async def init_db(self):
        async with aiosqlite.connect(self.db_file) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS sent_contests (
                    contest_id TEXT PRIMARY KEY,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            try:
                await db.execute("ALTER TABLE sent_contests ADD COLUMN status TEXT")
            except Exception:
                pass
            await db.execute('''
                CREATE TABLE IF NOT EXISTS guild_config (
                    guild_id TEXT PRIMARY KEY,
                    channel_id TEXT,
                    role_id TEXT
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS user_subscriptions (
                    user_id TEXT,
                    resource_id INTEGER,
                    PRIMARY KEY (user_id, resource_id)
                )
            ''')
            await db.commit()

    async def load_memory(self):
        async with aiosqlite.connect(self.db_file) as db:
            async with db.execute('SELECT contest_id, status FROM sent_contests') as cursor:
                rows = await cursor.fetchall()
        return {row[0]: row[1] for row in rows}

    async def save_memory(self, contest_id, status="registration_sent"):
        try:
            async with aiosqlite.connect(self.db_file) as db:
                await db.execute('INSERT OR REPLACE INTO sent_contests (contest_id, status) VALUES (?, ?)', (str(contest_id), status))
                await db.commit()
            self.sent_reminders[str(contest_id)] = status
        except Exception as e:
            logger.error(f"DB Save Error: {e}")

    async def setup_hook(self):
        self.session = aiohttp.ClientSession(headers={"Accept": "application/json"})
        await self.init_db()
        self.sent_reminders = await self.load_memory()
        
        self.add_view(RoleToggleView())
        self.reminder_patrol.start()
        self.daily_announcement.start()
        logger.info("Syncing slash commands...")
        self.tree.add_command(ConfigGroup(self))
        await self.tree.sync()
        
        # Railway Web Service Health Check
        from aiohttp import web
        app = web.Application()
        app.router.add_get('/', lambda r: web.Response(text="CronBot is active!"))
        runner = web.AppRunner(app)
        await runner.setup()
        port = int(os.environ.get("PORT", 8080))
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        logger.info(f"Health check server listening on port {port}")

    async def close(self):
        if hasattr(self, 'session') and self.session:
            await self.session.close()
        await super().close()

    async def on_ready(self):
        logger.info(f"{self.user.name} is online. @everyone pings active.")

    async def fetch_contests(self):
        now = (datetime.now(UTC) - timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M:%S')
        params = {
            "username": CLIST_USER,
            "api_key": CLIST_KEY,
            "resource_id__in": RESOURCES,
            "start__gte": now,
            "order_by": "start",
            "format": "json",
            "limit": 50
        }
        url = "https://clist.by/api/v2/contest/"
        
        try:
            async with self.session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get('objects', [])
                logger.error(f"CLIST API Error: {resp.status}")
                return None
        except Exception as e:
            logger.error(f"Fetch Error: {e}")
            return None

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
            except Exception:
                continue
        
        embed.description = "\n".join(lines)
        embed.set_footer(text="CronBot • Auto-localized")
        return embed

    @tasks.loop(minutes=1)
    async def reminder_patrol(self):
        await self.wait_until_ready()
        
        all_objects = await self.fetch_contests()
        if all_objects is None:
            logger.warning("Skipping patrol due to API error. Retaining current memory state.")
            return

        filtered_contests = self.filter_menu(all_objects)
        now = datetime.now(UTC)
        
        # Pull Configs & Subs
        async with aiosqlite.connect(self.db_file) as db:
            async with db.execute("SELECT guild_id, channel_id, role_id FROM guild_config") as cursor:
                guild_configs = await cursor.fetchall()
            async with db.execute("SELECT user_id, resource_id FROM user_subscriptions") as cursor:
                subscriptions = await cursor.fetchall()
        
        subs_by_resource = {}
        for uid, rid in subscriptions:
            subs_by_resource.setdefault(rid, []).append(uid)
        
        # 1. Cleanup Memory
        active_ids = {str(c['id']) for c in all_objects}
        to_remove = [rid for rid in self.sent_reminders.keys() if rid not in active_ids]
        if to_remove:
            async with aiosqlite.connect(self.db_file) as db:
                await db.executemany('DELETE FROM sent_contests WHERE contest_id = ?', [(r,) for r in to_remove])
                await db.commit()
            self.sent_reminders = {rid: status for rid, status in self.sent_reminders.items() if str(rid) in active_ids}
        
        # 2. Check for Reminders (Multi-Stage)
        for c in filtered_contests:
            start_dt = datetime.fromisoformat(c['start'].replace('Z', '')).replace(tzinfo=UTC)
            diff = (start_dt - now).total_seconds() / 60
            c_id = str(c['id'])
            status = self.sent_reminders.get(c_id)
            c_res = c['resource_id']
            
            # Tier 1: 30 Min Registration Alert (Fallback window: 8 to 35 mins)
            if 8 < diff <= 35 and status is None:
                embed = self.create_embed([c], is_reminder=True)
                view = RegisterView(c['href'])
                
                # Send to guilds
                for g_id, ch_id, r_id in guild_configs:
                    if not ch_id: continue
                    channel = self.get_channel(int(ch_id))
                    if channel:
                        ping_text = f"<@&{r_id}>" if r_id else "@everyone"
                        try: 
                            await channel.send(content=f"{ping_text} 🔔 **Registration open!** Starts in roughly 30m.", embed=embed, view=view)
                        except discord.Forbidden:
                            logger.warning(f"Missing permissions to send in channel {ch_id}")
                        except Exception as e:
                            logger.warning(f"Error sending guild msg to {ch_id}: {e}")
                
                # Send to DM subscribers
                for uid in subs_by_resource.get(c_res, []):
                    try:
                        user = self.get_user(int(uid)) or await self.fetch_user(int(uid))
                        if user: 
                            await user.send(content="🔔 **Registration open!** Starts in roughly 30m.", embed=embed, view=view)
                    except discord.Forbidden:
                        logger.warning(f"Cannot DM user {uid} (DMs closed)")
                    except Exception as e:
                        logger.warning(f"Error sending DM to {uid}: {e}")
                    await asyncio.sleep(0.05)  # Rate limiting protection
                        
                await self.save_memory(c_id, "registration_sent")
                
    @tasks.loop(time=time(hour=2, minute=0, tzinfo=UTC))
    async def daily_announcement(self):
        await self.wait_until_ready()
        all_objects = await self.fetch_contests()
        if not all_objects:
            return

        filtered_contests = self.filter_menu(all_objects)
        now = datetime.now(UTC)
        
        todays_contests = []
        for c in filtered_contests:
            start_dt = datetime.fromisoformat(c['start'].replace('Z', '')).replace(tzinfo=UTC)
            # Include contests in the next 24 hours
            if now <= start_dt <= now + timedelta(days=1):
                todays_contests.append(c)
                
        if not todays_contests:
            return
            
        embed = discord.Embed(
            title="📅 Welcome to Today's CP Calendar!",
            description="Good morning! Here are the contests happening in the next 24 hours.",
            color=0x2b2d31
        )
        lines = []
        for c in todays_contests:
            try:
                ts = int(datetime.fromisoformat(c['start'].replace('Z', '')).replace(tzinfo=UTC).timestamp())
                brand_info = self.branding.get(c['resource_id'], {"icon": "•"})
                lines.append(f"{brand_info['icon']} **[{c['event']}]({c['href']})**\n┕ <t:{ts}:t> (<t:{ts}:R>)\n")
            except Exception:
                continue
                
        if lines:
            embed.description += "\n\n" + "\n".join(lines)
        else:
            return

        embed.set_footer(text="CronBot • Daily Digest")

        async with aiosqlite.connect(self.db_file) as db:
            async with db.execute("SELECT guild_id, channel_id, role_id FROM guild_config") as cursor:
                guild_configs = await cursor.fetchall()
                
        # Send strictly to channels for the daily digest
        for g_id, ch_id, r_id in guild_configs:
            if not ch_id: continue
            channel = self.get_channel(int(ch_id))
            if channel:
                ping_text = f"<@&{r_id}>" if r_id else "@everyone"
                try:
                    await channel.send(content=f"🌅 {ping_text} **Daily Digest!**", embed=embed)
                except discord.Forbidden:
                    logger.warning(f"Missing permissions for daily digest in channel {ch_id}")
                except Exception as e:
                    logger.warning(f"Daily digest failed to send to {ch_id}: {e}")

bot = CronBot()

@bot.tree.command(name="ping", description="Check latency")
async def ping_slash(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 `{round(bot.latency * 1000)}ms`", ephemeral=True)

@bot.tree.command(name="contests", description="Show upcoming CP contests")
async def contests_slash(interaction: discord.Interaction):
    await interaction.response.defer()
    data = await bot.fetch_contests()
    if data is None:
        await interaction.followup.send("❌ Failed to fetch contests from the API. Please try again later.")
        return
    embed = bot.create_embed(data)
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="test_reminder", description="Preview reminder visuals")
@app_commands.checks.has_permissions(manage_guild=True)
async def test_reminder(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    data = await bot.fetch_contests()
    if data is None:
        await interaction.followup.send("❌ Failed to fetch contests from the API.")
        return
    
    filtered = bot.filter_menu(data)
    if filtered:
        async with aiosqlite.connect(bot.db_file) as db:
            async with db.execute("SELECT role_id FROM guild_config WHERE guild_id = ?", (str(interaction.guild_id),)) as cursor:
                row = await cursor.fetchone()
        
        ping_text = f"<@&{row[0]}>" if row and row[0] else "@everyone"
        embed = bot.create_embed([filtered[0]], is_reminder=True)
        view = RegisterView(filtered[0]['href'])
        await interaction.followup.send(content=f"{ping_text} 🧪 **Test Preview:**", embed=embed, view=view)
    else:
        await interaction.followup.send("No contests found to test.")

@bot.tree.command(name="subscribe", description="Subscribe to receive DMs for contests")
@app_commands.choices(platform=[
    app_commands.Choice(name="Codeforces", value=1),
    app_commands.Choice(name="CodeChef", value=2),
    app_commands.Choice(name="AtCoder", value=93)
])
async def subscribe_slash(interaction: discord.Interaction, platform: app_commands.Choice[int]):
    async with aiosqlite.connect(bot.db_file) as db:
        await db.execute('INSERT OR IGNORE INTO user_subscriptions (user_id, resource_id) VALUES (?, ?)', (str(interaction.user.id), platform.value))
        await db.commit()
    await interaction.response.send_message(f"✅ Subscribed to {platform.name} DMs!", ephemeral=True)

@bot.tree.command(name="unsubscribe", description="Unsubscribe from contest DMs")
@app_commands.choices(platform=[
    app_commands.Choice(name="Codeforces", value=1),
    app_commands.Choice(name="CodeChef", value=2),
    app_commands.Choice(name="AtCoder", value=93)
])
async def unsubscribe_slash(interaction: discord.Interaction, platform: app_commands.Choice[int]):
    async with aiosqlite.connect(bot.db_file) as db:
        await db.execute('DELETE FROM user_subscriptions WHERE user_id=? AND resource_id=?', (str(interaction.user.id), platform.value))
        await db.commit()
    await interaction.response.send_message(f"✅ Unsubscribed from {platform.name} DMs.", ephemeral=True)

if __name__ == "__main__":
    bot.run(TOKEN)
