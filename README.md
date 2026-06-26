# 🔐 OTP Manager Bot

A production-ready Telegram bot that manages multiple user sessions and fetches OTPs from Telegram's official account (`777000`) on demand. Built with **Pyrogram**, **Motor (MongoDB)**, and **aiohttp**, deployable on **Koyeb** free tier.

---

## ✨ Features

- **Multi-session management** — store and manage hundreds of Telegram string sessions
- **OTP fetching** — connect to any saved session and extract the latest OTP from `777000`
- **New message detection** — tracks last seen message ID, reports "no new OTP" if nothing changed
- **Paginated account list** — 20 accounts per page with inline keyboard navigation
- **Search** — find accounts by phone number or username
- **Session health check** — bulk-verify all sessions and auto-mark dead ones
- **Statistics** — total / active / invalid / dead session counts
- **Auto-delete OTP messages** — configurable delay via env var
- **Koyeb-ready** — aiohttp web server on port 8080 with `/ping` and `/restart` endpoints
- **Admin-only** — every command and callback is locked to a single `ADMIN_ID`

---

## 📁 Project Structure

```
otp_bot/
│
├── bot.py              # Pyrogram client + aiohttp web server (port 8080)
├── main.py             # Entry point
├── config.py           # Environment variable loader
├── database.py         # Motor/MongoDB wrapper (users + sessions collections)
├── generate.py         # /login and /logout handlers
│
├── handlers/
│   ├── __init__.py
│   ├── start.py        # /start command
│   ├── getotp.py       # /getotp, /stats, /search, /healthcheck commands
│   └── callbacks.py    # All inline keyboard callbacks
│
├── utils/
│   ├── __init__.py
│   ├── otp.py          # Session connect, OTP extraction logic
│   ├── paginator.py    # Inline keyboard builder with pagination
│   └── logger.py       # Logging setup
│
├── Dockerfile
├── .dockerignore
├── requirements.txt
└── .env.example
```

---

## ⚙️ Environment Variables

Copy `.env.example` to `.env` and fill in the values.

| Variable | Required | Description |
|---|---|---|
| `API_ID` | ✅ | Telegram API ID from [my.telegram.org](https://my.telegram.org) |
| `API_HASH` | ✅ | Telegram API Hash from [my.telegram.org](https://my.telegram.org) |
| `BOT_TOKEN` | ✅ | Bot token from [@BotFather](https://t.me/BotFather) |
| `ADMIN_ID` | ✅ | Your Telegram numeric user ID |
| `DB_URI` | ✅ | MongoDB connection URI (Atlas or self-hosted) |
| `DB_NAME` | ✅ | MongoDB database name (e.g. `otp_manager`) |
| `PORT` | ❌ | Web server port (default: `8080`) |
| `OTP_AUTO_DELETE` | ❌ | Seconds before OTP message is deleted (default: `0` = disabled) |

---

## 🚀 Deployment

### Local (with `.env`)

```bash
pip install python-dotenv
# Add `from dotenv import load_dotenv; load_dotenv()` at the top of config.py
python main.py
```

### Docker

```bash
docker build -t otp-bot .
docker run -d \
  -e API_ID=... \
  -e API_HASH=... \
  -e BOT_TOKEN=... \
  -e ADMIN_ID=... \
  -e DB_URI=... \
  -e DB_NAME=otp_manager \
  -p 8080:8080 \
  otp-bot
```

### Koyeb

1. Push your code to a GitHub repository.
2. Create a new **Web Service** on [Koyeb](https://app.koyeb.com).
3. Select your repo → Koyeb auto-detects the `Dockerfile`.
4. Set all environment variables in the **Environment** tab.
5. Set the **Port** to `8080`.
6. Deploy — Koyeb will hit `GET /` for health checks automatically.

> **Tip:** Use the `GET /restart` endpoint to trigger a live restart without redeploying.

---

## 🤖 Bot Commands

| Command | Description |
|---|---|
| `/start` | Show available commands |
| `/login` | Add a new Telegram account (interactive flow) |
| `/logout` | Remove your current session |
| `/getotp` | Show all saved accounts and fetch OTPs |
| `/stats` | Session statistics |
| `/healthcheck` | Verify all sessions and mark dead ones |
| `/search <query>` | Search accounts by phone number or username |

---

## 🔘 Inline Keyboard Actions

After `/getotp`, you can:

- **Click an account** → fetches the latest OTP from `777000`
- **🔄 Refresh OTP** → re-fetches without closing the message
- **◀ / ▶ navigation** → page through accounts
- **🔍 Search Phone / Name** → search inline
- **📊 Stats** → quick statistics
- **🏥 Health Check** → bulk session check

---

## 🛡️ OTP Detection

The bot reads only messages from chat ID `777000` and detects:

- `Login code: 48392`
- `Your Telegram code: 12345`
- `Confirmation code: ...`
- `Two-step verification code`

It extracts the numeric OTP and also sends the full raw message so nothing is missed.

---

## 🗄️ Database Schema

### `sessions` collection

| Field | Type | Description |
|---|---|---|
| `user_id` | int | Telegram user ID |
| `user_name` | str | Username or display name |
| `string_session` | str | Pyrogram string session |
| `phone_number` | str | Phone number with country code |
| `date_added` | datetime | When the session was added |
| `last_checked` | datetime | Last OTP fetch time |
| `status` | str | `active` / `invalid` / `dead` |
| `last_message_id` | int | Last seen message ID from 777000 |

---

## 📦 Requirements

- Python 3.11+
- MongoDB (Atlas free tier works)
- Telegram API credentials

```
pyrogram==2.0.106
TgCrypto
motor
pymongo
aiohttp
bson
```

---

## ⚠️ Security Notes

- String sessions grant **full access** to a Telegram account. Keep your `DB_URI` private.
- Never commit `.env` or `.session` files to version control.
- The bot ignores all messages from non-admin users entirely.
- The `/restart` web endpoint has no auth — restrict network access if needed.

---

## 📝 Credits

Login/logout flow based on original work by [@VJ_Botz](https://t.me/VJ_Botz).
