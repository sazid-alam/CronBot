<div align="center">
  <h1>CronBot</h1>
  <p>A highly resilient, multi-platform Competitive Programming Discord Bot built for active clubs and servers.</p>
</div>

## ✨ Features
- **Intelligent Platform Sieve**: Fetches and aggregates only the highest quality rated rounds from **Codeforces (Div. 2/3/4, Edu)**, **CodeChef (Starters)**, and **AtCoder (Beginner)**.
- **Multi-Staged Smart Alerts**: Dynamically tracks upcoming contests and sends overlapping, fail-safe alerts at:
  - 🔔 **T-30 Minutes**: Registration reminders with a direct platform link.
  - ⚠️ **T-5 Minutes**: Final "get seated" warning to prepare templates.
- **Robust Persistence (SQLite)**: Fully abstracts memory states into a `cronbot.db` SQLite database, ensuring reminder loops mathematically guarantee delivery and never repeat an alert, even after cloud server re-deployments. 
- **Admin Setup Commands**: Fully customizable from within Discord via slash commands (`/config`), eliminating the need for hardcoded `.env` files.
- **Personal Subscriptions**: Users can opt-in to personalized direct messages via `/subscribe` for any specific platform, keeping the main channels clean while ensuring participants don't miss out.
- **Cloud Ready**: Configured natively for PaaS environments like Railway with an internal un-threaded `aiohttp` web server to seamlessly satisfy deployment port health checks.

## 🛠 Commands
**Admin Settings** *(Requires `Administrator` permissions)*:
- `/config set_channel #channel` — Defines which text channel the bot broadcasts general alerts to.
- `/config set_ping_role @role` — Sets a specific role (e.g., `@CP-Hustlers`) to mention instead of the default `@everyone`.

**General Interactions**:
- `/contests` — Instantly pulls up an embedded schedule of the top 10 upcoming quality rounds.
- `/subscribe [Platform]` — Opts the user into direct message alerts for a chosen platform (Codeforces, CodeChef, AtCoder).
- `/unsubscribe [Platform]` — Removes the user from direct message alerts.
- `/ping` — Checks the bot's current API latency.

## 🚀 Deployment (Railway / Docker)
CronBot is heavily optimized for seamless PaaS deployment.
1. Fork or clone the repository.
2. Provide your Environment Variables:
   - `DISCORD_TOKEN` = Your Discord bot token.
   - `CLIST_USERNAME` = Your Clist.by competitive programming API username.
   - `CLIST_API_KEY` = Your Clist.by API key.
3. Deploy directly using the provided `Dockerfile`. 
   - *Note: Railway Web Services natively pass Health Checks automatically within 60s via the bot's injected asynchronous web process.*

## 💻 Local Development
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```
