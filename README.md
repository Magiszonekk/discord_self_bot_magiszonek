# Discord Status Rotations

Discord self-bot that rotates curated custom statuses, manages community submissions, and pings you the moment a tracked Twitch broadcaster goes live. SQLite keeps the state, `discord.py-self` powers the client, and a single process handles CLI input, Discord commands, and Twitch EventSub events.

> ⚠️ Discord self-bots violate Discord's Terms of Service. Run this only on accounts you accept losing and preferably on a throwaway profile.

## What you get
- **Web Panel** – React-based dashboard for managing the bot without Discord commands.
- **Multi-user auth** – Admin and user accounts with permissions. Honeypot feature for monitoring unauthorized DM attempts.
- **Brute force protection** – IP-based login throttling (5 attempts = 15 min block).
- **Database backups** – Automatic daily backups with 7-day retention.
- Automatic rotation of approved statuses every 25–45 minutes with manual override and enable/disable switches.
- Status submission workflow with categories, per-user lists, and owner approvals driven by a 👍 reaction on `!add_status` messages.
- Permission gates so only trusted IDs can interact with the workflow, plus owner-only admin and logging commands.
- Background CLI thread for simple console housekeeping (`cls` / `csl`) without interrupting the asyncio loop.
- Twitch EventSub listener that reconnects automatically and DMs the configured Discord user with the live stream URL.
- Log aggregation into `logs/bot.log` with an in-Discord `!logs` command for quick forensics.
- Helpers for DMing or posting updates to channels, ready for custom automation beyond Twitch alerts.

## Project layout
- `main.py` – entry point; loads `.env`, initializes the database, creates default users, and starts the web server.
- `web_app.py` – FastAPI backend with REST API, authentication, brute force protection, and backup scheduler.
- `discord_actions.py` – on-demand Discord client for status changes, DMs, and fetching recent conversations.
- `discord_module.py` – `discord.py-self` client with command handlers, rotation logic, Twitch glue, logging hooks, and DM/channel helpers.
- `db_utils.py` – SQLite helpers for statuses, categories, permissions, users, and fake DMs (honeypot).
- `backup_utils.py` – database backup and cleanup utilities.
- `is_live.py` – Twitch EventSub websocket client plus REST helper to look up broadcaster IDs.
- `logging_utils.py` – file logger, log-tail helper, and Discord command handler for serving log slices.
- `frontend/` – Next.js React dashboard (run `npm install && npm run build` inside).
- `backups/` – automatic database backups (ignored by Git).
- `bot_data.db` – SQLite database; delete it to reset (new admin password will be generated).
- `.env` – local environment variables (ignored by Git).

## Requirements
- Python 3.10+ (CPython tested).
- `pip`, `virtualenv`, and SQLite (bundled with Python).
- Node.js 18+ and npm (for the web panel frontend).
- A Discord user token you control (see ToS warning).
- Twitch Application client ID + OAuth token if you use the go-live watcher.

## Quick start
1. **Clone and enter the repo.**
2. **Create a virtual environment and install dependencies:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. **Build the frontend (optional, for web panel):**
   ```bash
   cd frontend
   npm install
   npm run build
   cd ..
   ```
4. **Create `.env`** with the variables below (only keep the ones you need).
5. **Run the bot**:
   ```bash
   python main.py
   ```
   On first run, the admin password is printed to console—**save it immediately**.
   The web panel is available at `http://localhost:3003`.

### Environment variables
```dotenv
# Discord
TOKEN="discord-user-token"
BROADCAST_NOTIFY_USER_ID="123456789012345678"
DEBUG_CHANNEL_ID="123456789012345678"

# Web Panel
WEB_HOST="0.0.0.0"
WEB_PORT="3003"
SESSION_SECRET="your-secret-key"

# Twitch (optional)
BOT_CLIENT_ID="twitch-client-id"
BOT_ACCESS_TOKEN="twitch-oauth-token"
BROADCASTER="twitch-login-to-watch"

# Logging
LOG_DIR="logs"
LOG_FILE_NAME="bot.log"
ENVIRONMENT="development"
```

- `TOKEN` – Discord user token consumed by `discord.py-self`.
- `BROADCAST_NOTIFY_USER_ID` – Discord ID that should receive Twitch notifications (usually your own account).
- `DEBUG_CHANNEL_ID` – optional channel ID for custom debug posts via `send_channel_message`.
- `WEB_HOST` – host for the web panel (default `0.0.0.0`).
- `WEB_PORT` – port for the web panel (default `3003`).
- `SESSION_SECRET` – secret key for session encryption. Generate a strong random value.
- `BOT_CLIENT_ID` and `BOT_ACCESS_TOKEN` – Twitch app credentials with EventSub permissions.
- `BROADCASTER` – Twitch login you want to monitor. Leave unset to skip the watcher.
- `LOG_DIR` / `LOG_FILE_NAME` – override the default log destination (`logs/bot.log`).
- `ENVIRONMENT` – informational flag if you want different behavior per env.

Store `.env` outside of version control. If you need multiple deployments, keep separate `.env` files per machine.

## Web Panel

The web panel runs on `http://localhost:3003` by default and provides a React-based dashboard for managing the bot.

### Default users
On first run, the system creates two accounts:
- **admin** – full access. Password is randomly generated and printed to console once. Save it immediately.
- **user** – limited access (cannot send real DMs). Default password: `admin123`.

### Changing passwords
```python
from db_utils import change_user_password
change_user_password("admin", "new-password")
```

### Permission system
Permissions are stored as a JSON array. Special values:
- `"all"` – grants all permissions.
- `"-send_dm"` – revokes DM sending (negative permission).
- `"admin"` – grants access to admin-only endpoints.

The `user` account has `["all", "-send_dm"]` by default, meaning it can do everything except send real DMs.

### Honeypot feature
When a user without DM permission tries to send a message:
1. The system pretends the DM was sent successfully.
2. The message is saved to the `fake_dms` table for review.
3. A warning is logged: `[HONEYPOT] User 'x' tried to DM y: message`.

Admins can review honeypot entries via the `/api/admin/fake-dms` endpoint.

### Security features
- **Brute force protection** – 5 failed login attempts from the same IP triggers a 15-minute block.
- **Session-based auth** – credentials are not stored in browser storage.
- **Daily backups** – database is backed up at startup and every 24 hours to `backups/`.

## Database
- `db_utils.init_db()` creates tables inside `bot_data.db`:
  - `status_requests` – tracks `person_name`, `person_id`, `status`, `category`, and `approved_by_user_id`. Unapproved rows stay out of the rotation pool until the owner reacts with thumbs up.
  - `categories` – user-defined labels for filtering submissions.
  - `permissions` – trusted Discord IDs and optional labels for auditing.
  - `users` – web panel accounts with bcrypt-hashed passwords and permissions.
  - `fake_dms` – honeypot table storing unauthorized DM attempts.
- Delete `bot_data.db` to reset everything; you'll lose all data and a new admin password will be generated.

## Runtime behavior
- `MyClient` loads approved statuses at startup and schedules `rotate_status_task`, which sleeps a random 25–45 minutes between updates. Use `!change_status` to force an immediate refresh.
- `!rotate_status` flips the rotation boolean so you can pause updates without stopping the process.
- `test_eventsub` connects to Twitch EventSub, subscribes to the `stream.online` topic for `BROADCASTER`, and calls `send_discord_message` with the Twitch URL when it fires. Auto-reconnect handles keepalive gaps and rate limiting.
- `!vedal_loop` toggles the internal `vedal_loop` flag, ready for wiring into additional watcher logic.
- `parse_message_content` and `vedal_reaction` showcase lightweight keyword reactions (currently responds with ❤️ to a private meme phrase when it comes from `BROADCAST_NOTIFY_USER_ID`).
- The background CLI thread keeps your terminal tidy without interrupting the asyncio event loop.

## Logging and observability
- `logging_utils.log` writes timestamped entries to `LOG_DIR/LOG_FILE_NAME` (default `logs/bot.log`) and can optionally print to stdout.
- Admins can fetch logs directly from Discord with:
  - `!logs` – last 10 lines.
  - `!logs 25` – last _n_ lines.
  - `!logs 50 26-11 10:41[:07]` – returns 50 lines closest to the provided `day-month hour:minute[:second]`.
- The helper clamps long output to Discord’s 2 000 character limit and mirrors every request in the log file for auditing.

## Discord commands
All commands work in DMs or guild channels where your self-bot can post. The owner (your user ID) is implicitly trusted; additional IDs must be added via `!add_permission`.

**General**
- `!help` – list public commands.
- `!help 2` – list owner/admin commands.
- `!ping` – sanity check (`pong`).
- `!change_status` – set a new random approved status immediately.
- `!rotate_status` – enable/disable automatic rotation (owner only).
- `!vedal_loop` – toggle the Twitch watcher flag (owner only).

**Status workflow**
- `!status_list <category>` – show approved statuses in a category.
- `!my_status_list` – list every submission you have made (IDs + approval state).
- `!my_status_list <category>` – narrow the list to one category.
- `!add_status <category> <status text>` – submit a new status for approval.
- `!remove_status <status_id>` – delete one of your submissions (must match the numeric ID shown above).
- Owner reacts with 👍 on a `!add_status` message to approve it.

**Category management**
- `!category_list` – display every category label.
- `!add_category <label>` – create a category (single word).
- `!remove_category <label>` – remove a category you created.

**Permissions (owner only)**
- `!permissions_list` – print all IDs with elevated access.
- `!add_permission <user_id> <label>` – grant access and tag it with a label for context.
- `!remove_permission <user_id>` – revoke a user.

**Logs (owner only)**
- `!logs [how_many] [day-month hour:minute[:second]]` – send the tail of `logs/bot.log` or the lines closest to the provided timestamp. Arguments are optional as described in the logging section above.

## Custom triggers
`vedal_reaction` in `discord_module.py` is a template for meme-y reactions. When the tracked user posts a message that reduces to `ty chuju`/`ty huju`, the bot reacts with ❤️. Replace the trigger list to bolt on moderation tools or inside jokes.

## Extending the bot
- `send_discord_message` and `send_channel_message` provide reusable plumbing for DMing Twitch pings, status alerts, or anything else from background tasks.
- Add new background tasks in `on_ready` and guard them with `bg_tasks_started` booleans to avoid duplicate scheduling.
- Update `db_utils.init_db()` and document migration steps if you modify the schema so fresh installs and existing databases stay aligned.

## Development tips
- Never commit your `.env` file—share a sanitized template instead.
- Run the bot on an alternate Discord account to avoid risking your primary profile.
- SQLite is file-based. Stop the process before copying or editing `bot_data.db` with external tools.

## License
No license is included. Add one before distributing or taking contributions.
