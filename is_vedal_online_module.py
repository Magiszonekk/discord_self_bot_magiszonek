import asyncio
import aiohttp
from datetime import datetime, timedelta

URL = "https://decapi.me/twitch/uptime/vedal987"

START_HOUR = 20
END_HOUR = 22

PHASE1_END = 15   # until 20:15 -> every 1 min
PHASE2_END = 30   # until 20:30 -> every 2 min
# afterwards -> every 5 min

def in_time_window(now: datetime) -> bool:
    start = now.replace(hour=START_HOUR, minute=0, second=0, microsecond=0)
    end = now.replace(hour=END_HOUR, minute=0, second=0, microsecond=0)
    return start <= now < end

def minutes_since_start(now: datetime) -> int:
    start = now.replace(hour=START_HOUR, minute=0, second=0, microsecond=0)
    diff = now - start
    return diff.seconds // 60

def calc_sleep_seconds(now: datetime) -> int:
    mins = minutes_since_start(now)

    if mins < PHASE1_END:
        return 60         # 1 min
    elif mins < PHASE2_END:
        return 120        # 2 min
    else:
        return 300        # 5 min

def seconds_until_next_day_window(now: datetime) -> int:
    # tomorrow at 20:00
    tomorrow = now.date() + timedelta(days=1)
    next_start = datetime(
        year=tomorrow.year,
        month=tomorrow.month,
        day=tomorrow.day,
        hour=START_HOUR,
        minute=0,
        second=0,
        microsecond=0
    )
    return int((next_start - now).total_seconds())

def seconds_until_next_window(now: datetime) -> int:
    today_start = now.replace(hour=START_HOUR, minute=0, second=0, microsecond=0)
    today_end = now.replace(hour=END_HOUR, minute=0, second=0, microsecond=0)

    if now < today_start:
        # before 20:00 -> sleep until today at 20:00
        return int((today_start - now).total_seconds())
    elif now >= today_end:
        # after 22:00 -> sleep until tomorrow at 20:00
        return seconds_until_next_day_window(now)
    else:
        # we shouldn't end up here while inside the window
        return 0

async def vedal_watch_loop(client_ref, startup_time: datetime):
    """
    client_ref = MyClient instance (Discord client),
    used to send a notification once per day.
    """
    session_timeout = aiohttp.ClientTimeout(total=10)

    async with aiohttp.ClientSession(timeout=session_timeout) as session:
        while client_ref.vedal_loop:
            now = datetime.now()

            if should_skip_today(startup_time, now):
                sleep_s = seconds_until_next_day_window(now)
                # print(f"[{now:%H:%M:%S}] 🚫 Bot started after 20:00 today, skipping. Sleeping {sleep_s}s until tomorrow 20:00")
                await asyncio.sleep(sleep_s)
                continue

            # if we've already sent today's notification -> sleep until tomorrow 20:00
            if client_ref.already_notified_today:
                sleep_s = seconds_until_next_day_window(now)
                # print(f"[{now:%H:%M:%S}] ✅ Already notified today. Sleeping {sleep_s}s until tomorrow 20:00")
                client_ref.already_notified_today = False  # reset after sleeping
                await asyncio.sleep(sleep_s)
                continue

            # if we're outside the 20-22 window -> sleep until it starts
            if not in_time_window(now):
                sleep_s = seconds_until_next_window(now)
                # print(f"[{now:%H:%M:%S}] Outside the window. Sleeping {sleep_s}s until the next one.")
                await asyncio.sleep(sleep_s)
                continue

            # we are inside the window -> perform the check
            try:
                print(f"[{now:%H:%M:%S}] 🔎 Request -> {URL}")
                async with session.get(URL) as resp:
                    body = (await resp.text()).lower()

                if "offline" not in body:
                    # Vedal is live -> send a DM once
                    print(f"[{now:%H:%M:%S}] 🎉 Vedal is live!")
                    await client_ref.send_discord_message("https://www.twitch.tv/vedal987")
                    client_ref.already_notified_today = True
                    # and on the next loop iteration we'll sleep until tomorrow
                    continue
                else:
                    print(f"[{now:%H:%M:%S}] ❄ still offline")

            except Exception as e:
                print(f"[{now:%H:%M:%S}] 💀 request error: {e}")

            delay = calc_sleep_seconds(datetime.now())
            print(f"[{datetime.now():%H:%M:%S}] waiting {delay}s until the next check\n")
            await asyncio.sleep(delay)

def should_skip_today(startup_time: datetime, now: datetime) -> bool:
    """
    Returns True if:
    - the bot started today
    - and it started after 20:00
    In that case we skip the requests for the rest of the day.
    Tomorrow -> back to normal.
    """
    same_day = (startup_time.date() == now.date())
    started_after_20 = startup_time.hour >= START_HOUR
    return same_day and started_after_20
