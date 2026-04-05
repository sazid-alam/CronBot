# CronBot 🤖⏰

A Discord bot that tracks upcoming competitive programming contests and pings your server **30 minutes before they start** — so you never miss a round.

Supports **Codeforces**, **CodeChef**, and **AtCoder**, filtered to beginner-friendly and educational rounds.

---

## Features

- **Automatic reminders** — monitors contests every minute and sends an `@everyone` alert ~30 minutes before a contest begins.
- **`/contests`** — slash command that lists all upcoming filtered contests with timestamps auto-localized to each user's timezone.
- **`/ping`** — check the bot's latency.
- **`/test_reminder`** — preview what a reminder embed looks like (ephemeral, only visible to you).
- **Duplicate-safe** — remembers which reminders have already been sent (persisted to `sent_reminders.json`) so it never double-pings.
- **Health check endpoint** — exposes a `/` HTTP route (Flask) so uptime monitors (e.g. UptimeRobot) can keep the process alive.

---

## Supported Platforms & Filters

| Platform     | Resource ID | Filter |
|--------------|-------------|--------|
| Codeforces   | 1           | Div. 1+2, Div. 2, Div. 3, Div. 4, Educational |
| CodeChef     | 2           | Starters |
| AtCoder      | 93          | Beginner contests |

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/sazid-alam/CronBot.git
cd CronBot
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Set environment variables

| Variable           | Description |
|--------------------|-------------|
| `DISCORD_TOKEN`    | Your Discord bot token (from the [Developer Portal](https://discord.com/developers/applications)) |
| `CLIST_USERNAME`   | Your [clist.by](https://clist.by) username |
| `CLIST_API_KEY`    | Your clist.by API key |
| `CHANNEL_ID`       | ID of the Discord channel where reminders will be posted |
| `PORT` *(optional)*| HTTP port for the health-check server (default: `8080`) |

### 4. Run the bot

```bash
python main.py
```

---

## Docker

A `Dockerfile` is included. Build and run with:

```bash
docker build -t cronbot .
docker run -e DISCORD_TOKEN=... -e CLIST_USERNAME=... -e CLIST_API_KEY=... -e CHANNEL_ID=... cronbot
```

> The container exposes port `7860` (suitable for Hugging Face Spaces deployments).

---

## Deployment (Hugging Face Spaces)

1. Create a new **Docker** Space on [huggingface.co/spaces](https://huggingface.co/spaces).
2. Push this repository to the Space.
3. Add all required environment variables as Space **Secrets**.
4. Optionally, point an uptime monitor at the Space URL (`/`) to prevent cold starts.

---

## Project Structure

```
CronBot/
├── main.py              # Bot logic, slash commands, reminder loop, health server
├── requirements.txt     # Python dependencies (discord.py, flask, aiohttp)
├── Dockerfile           # Container definition
├── cf.png               # Codeforces logo (used in embeds)
├── cc.png               # CodeChef logo
└── ac.png               # AtCoder logo
```

---

## How It Works

1. **`reminder_patrol`** task loop runs every minute.
2. It fetches upcoming contests from the [clist.by API](https://clist.by/api/v2/contest/) for the three supported platforms.
3. Contests are filtered by name to keep only beginner/educational rounds.
4. For each filtered contest starting in **20–30 minutes** that hasn't been announced yet, the bot sends an embed with:
   - Contest name and platform logo
   - Auto-localized start time and relative countdown
   - A **Register** button linking directly to the contest page
5. The contest ID is recorded so the reminder is not sent again.

---

## License

MIT
