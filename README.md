<div align="center">
  <h1>CronBot</h1>
  <p>A highly resilient, multi-platform Competitive Programming Discord Bot built for active clubs and servers.</p>
</div>

## ✨ Features
- **Intelligent Platform Sieve**: Fetches and aggregates only the highest quality rated rounds from:
  - 🟦 **Codeforces** — Div. 1+2, Div. 2, Div. 3, Div. 4, Educational rounds
  - 🟫 **CodeChef** — Starters
  - ⬛ **AtCoder** — Beginner contests
- **Multi-Staged Smart Alerts**: Dynamically tracks upcoming contests and sends overlapping, fail-safe alerts with generous fallback windows:
  - 🔔 **~30 Minutes out** *(window: 8–35 min)*: Registration reminders with a direct **Register on Platform** button.
  - ⚠️ **~5 Minutes out** *(window: 0–8 min)*: Final "get seated" warning to prepare templates.
- **Robust Persistence (SQLite)**: Fully abstracts memory states into a `cronbot.db` SQLite database, ensuring reminder loops mathematically guarantee delivery and never repeat an alert, even after cloud server re-deployments.
- **Admin Setup Commands**: Fully customizable from within Discord via slash commands (`/config`), eliminating the need for hardcoded `.env` files.
- **Self-Service Role Menu**: Admins can post a persistent button panel (`/config send_role_menu`) that lets members self-assign the contest ping role without any manual intervention.
- **Personal Subscriptions**: Users can opt-in to personalized direct messages via `/subscribe` for any specific platform, keeping main channels clean while ensuring participants never miss a contest.
- **Cloud Ready**: Ships an internal `aiohttp` web server to satisfy PaaS health checks (Railway, Hugging Face Spaces, etc.) without blocking the bot's async loop.

## 🛠 Commands

**Admin Settings** *(Requires `Manage Server` permission)*:
| Command | Description |
|---|---|
| `/config set_channel #channel` | Defines which text channel the bot broadcasts contest alerts to. |
| `/config set_ping_role @role` | Sets a role (e.g. `@CP-Hustlers`) to mention instead of `@everyone`. |
| `/config send_role_menu` | Posts a persistent button panel in the current channel so members can self-assign/remove the ping role. |
| `/config inspect` | Debug: dumps the current SQLite `guild_config` state (ephemeral). |

**General Interactions**:
| Command | Description |
|---|---|
| `/contests` | Instantly pulls up an embedded schedule of the top 10 upcoming quality rounds. |
| `/subscribe [Platform]` | Opts the user into direct-message alerts for Codeforces, CodeChef, or AtCoder. |
| `/unsubscribe [Platform]` | Removes the user from direct-message alerts. |
| `/ping` | Checks the bot's current WebSocket latency. |
| `/test_reminder` | Preview the reminder embed and register button using the next upcoming contest. |

**Self-Service Role Panel** *(sent via `/config send_role_menu`)*:
- ✅ **Get Role** — Assigns the configured ping role to the user.
- ❌ **Remove Role** — Removes the ping role from the user.
- 🔍 **Check Status** — Reports whether the user currently holds the ping role.

## 🚀 Deployment (Docker / Railway / HF Spaces)

CronBot is optimized for seamless PaaS deployment.

1. Fork or clone the repository.
2. Set the following **required** environment variables:

   | Variable | Description |
   |---|---|
   | `DISCORD_TOKEN` | Your Discord bot token. |
   | `CLIST_USERNAME` | Your [clist.by](https://clist.by) API username. |
   | `CLIST_API_KEY` | Your clist.by API key. |

3. Optionally configure:

   | Variable | Default | Description |
   |---|---|---|
   | `PORT` | `8080` | Port for the internal health-check web server. |
   | `DB_PATH` | `cronbot.db` | Path to the SQLite database file. |
   | `CHANNEL_ID` | `0` | Legacy fallback channel ID (prefer `/config set_channel`). |

4. Deploy using the provided `Dockerfile`.
   - The bot exposes port **7860** by default (Hugging Face Spaces compatible).
   - The internal `aiohttp` health-check server responds on `/` so Railway and HF Spaces pass health checks automatically within 60 s.

## 💻 Local Development
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

## 🧩 Dependencies
- [`discord.py`](https://github.com/Rapptz/discord.py) — Discord API wrapper with app_commands & tasks support.
- [`aiohttp`](https://docs.aiohttp.org/) — Async HTTP client (clist.by API calls) and health-check web server.
