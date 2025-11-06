# Discord Status Rotations

Lightweight Discord self-bot that rotates custom statuses, curates crowd-sourced status suggestions, and optionally watches a Twitch broadcaster for live notifications. Persistence is handled with SQLite, and a handful of Discord commands allow trusted users to manage categories, submissions, and permissions without touching the database.

> ⚠️ **Heads-up:** Discord self-bots violate Discord's Terms of Service. Run this code only on accounts you are willing to lose and at your own risk.

## Features
- Automatic rotation of approved custom statuses on a configurable random interval.
- Status suggestion workflow with categories, per-user tracking, and emoji-based approvals.
- Permission system so only trusted users can submit and curate statuses.
- Minimal CLI helper (clearing the console) that runs alongside the async Discord client.
- Twitch EventSub listener that prints when the configured broadcaster goes live.

## Project layout
- `main.py` – application entry point; loads environment, initializes the database, starts the CLI, and runs the Discord client.
- `discord_module.py` – `discord.py-self` client with background tasks, command handlers, reactions, and helper utilities.
- `db_utils.py` – SQLite helpers for statuses, categories, and permission records (stored in `bot_data.db`).
- `is_live.py` – Twitch EventSub websocket client plus REST helper to resolve user IDs.
- `cli.py` – background thread with a simple `cls` command for quick console cleanup.
- `.env` – runtime secrets and IDs (not committed).

## Requirements
- Python 3.10+ (tested with CPython).
- A Discord account token that you control (self-bot usage risk noted above).
- Twitch Application credentials if you plan to use the EventSub watcher.
- `pip` and `virtualenv` tooling.

## Quick start
1. **Clone the repo** and open the project directory.
2. **Create and activate a virtual environment** (matches `venv.txt`):
   ```powershell
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. **Create a `.env` file** in the project root (example below) and fill in the values for your setup.
4. **Run the bot**:
   ```powershell
   python main.py
   ```
   The CLI thread prints `CLI ready ...` and accepts `cls` to clear your console while the Discord client runs in the foreground.

### Environment variables
```dotenv
TOKEN="discord-user-token"
DEBUG_CHANNEL_ID="123456789012345678"
BROADCAST_NOTIFY_USER_ID="123456789012345678"
ENVIRONMENT="development"
BOT_ACCESS_TOKEN="twitch-oauth-access-token"
BOT_CLIENT_ID="twitch-application-client-id"
BROADCASTER="twitch-username-to-watch"
```

- `TOKEN` is your Discord user token used by `discord.py-self`.
- `DEBUG_CHANNEL_ID` is an optional channel where you can post debug output via helper methods.
- `BROADCAST_NOTIFY_USER_ID` is the account that should receive notifications when the watched streamer goes live.
- `ENVIRONMENT` flag for your custom logic (currently informational).
- `BOT_CLIENT_ID` and `BOT_ACCESS_TOKEN` come from your Twitch application and must have EventSub permissions.
- `BROADCASTER` is the Twitch login name whose live status you want to monitor.

### Database
- On first run `db_utils.init_db()` creates `bot_data.db` with tables for `status_requests`, `permissions`, and `categories`.
- Records persist between runs; delete `bot_data.db` if you need a fresh start (note: you will lose every stored status and permission).
- Emoji reactions in Discord can approve pending statuses (see command reference below).

## Running workload
- The status rotation task picks a random approved entry every 25–45 minutes and sets it as your custom status.
- `daily_status_task()` (not scheduled by default) demonstrates how to target a specific time of day if you want deterministic updates.
- `is_live.test_eventsub()` opens a websocket to Twitch and prints to the console whenever `BROADCASTER` goes live. Extend `MyClient` helpers to DM or post to channels if desired.

## Discord commands
All commands run in DMs to yourself (typical for self-bots) or in channels where your account can post. Only users listed in `permissions` may interact with the status workflow unless noted.

### General
- `!help` – display the public command list.
- `!help 2` – display the admin command list (owner only).
- `!ping` – health check (`pong`).
- `!change_status` – immediately pick a new random approved status.
- `!rotate_status` – toggle the automatic rotation task (owner only).
- `!vedal_loop` – toggle the Twitch watcher flag (owner only).

### Status management
- `!status_list <category>` – list approved statuses within a category.
- `!my_status_list` – list every status you have submitted (shows ID and approval state).
- `!my_status_list <category>` – narrow the list to a single category.
- `!add_status <category> <status text>` – submit a new status to a category. The entry stays pending until approved.
- `!remove_status <status_id>` – remove one of your submissions by its database ID.
- React with the bot's confirmation emoji on a `!add_status` message to mark it approved (self-bot account only).

### Category management
- `!category_list` – list all available categories.
- `!add_category <name>` – create a new category (single word).
- `!remove_category <name>` – delete a category you previously created.

### Permission management (owner only)
- `!permissions_list` – view every user with elevated permissions.
- `!add_permission <user_id> <label>` – grant a user access to status commands.
- `!remove_permission <user_id>` – revoke a user's permission.

## Custom triggers
Messages that match specific phrases (see `vedal_reaction` in `discord_module.py`) receive automatic emoji reactions, showcasing how to bolt on lightweight moderation or meme responses.

## Extending the bot
- Use `send_discord_message` and `send_channel_message` helpers in `MyClient` to deliver Twitch notifications to users or channels instead of just printing.
- Add new background tasks via `on_ready` once the client connects; remember to gate them with booleans like `bg_tasks_started` to avoid duplicates.
- If you change the schema, update `db_utils.init_db()` and provide migration steps for existing `bot_data.db` files.

## Development tips
- Keep secrets out of version control—use `.env` locally and share a sanitized template instead.
- Run the bot from an isolated account to avoid losing access to your main Discord profile.
- SQLite is file-based; close the app before copying or editing `bot_data.db` with external tools.

## License
A license has not been provided. Consider adding one before distributing or accepting outside contributions.
