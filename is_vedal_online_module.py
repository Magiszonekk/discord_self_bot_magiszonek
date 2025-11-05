import asyncio
import aiohttp
import json
import os
from datetime import datetime, timedelta

# --- KONFIG ---
# CHANNEL_LOGIN = "vedal987"  # <- kogo sprawdzasz
CHANNEL_LOGIN = "vedal987"
GQL_URL = "https://gql.twitch.tv/gql"
FRONTEND_CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"  # publiczny client-id frontendu
STREAM_METADATA_HASH = "1c719a40e481453e5c48d9bb585d971b8b372f8ebb105b17076722264dfa5b3e"

START_HOUR = 20
END_HOUR = 22
PHASE1_END = 15   # do 20:15 co 20 sec
PHASE2_END = 30   # do 20:30 co 2 min
PHASE3_END = 60   # do 21:00 co 5 min

PHASE4_END = 75   # do 21:15 co 1 min
PHASE5_END = 90   # do 21:30 co 2 min
# potem co 5 min

# --- UTIL ---
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
        return 20         # 20 sec
    elif mins < PHASE2_END:
        return 120        # 2 min
    elif mins < PHASE3_END:
        return 300        # 5 min
    elif mins < PHASE4_END:
        return 60         # 1 min
    elif mins < PHASE5_END:
        return 120        # 2 min
    else:
        return 300        # 5 min

def seconds_until_next_day_window(now: datetime) -> int:
    tomorrow = now.date() + timedelta(days=1)
    next_start = datetime(
        year=tomorrow.year, month=tomorrow.month, day=tomorrow.day,
        hour=START_HOUR, minute=0, second=0, microsecond=0
    )
    return int((next_start - now).total_seconds())

def seconds_until_next_window(now: datetime) -> int:
    today_start = now.replace(hour=START_HOUR, minute=0, second=0, microsecond=0)
    today_end = now.replace(hour=END_HOUR, minute=0, second=0, microsecond=0)
    if now < today_start:
        return int((today_start - now).total_seconds())
    elif now >= today_end:
        return seconds_until_next_day_window(now)
    else:
        return 0

def should_skip_today(startup_time: datetime, now: datetime) -> bool:
    environment = os.getenv("ENVIRONMENT")
    if environment != "production":
        return False
    same_day = (startup_time.date() == now.date())
    started_after_20 = startup_time.hour >= START_HOUR
    return same_day and started_after_20

# --- NIEOFICJALNE SPRAWDZANIE LIVE (aiohttp) ---
async def is_live_unofficial(session: aiohttp.ClientSession, channel_login: str) -> bool:
    """
    Pyta frontendowe GraphQL Twitcha (persisted query).
    Zwraca True, jeśli kanał wygląda na LIVE.
    """
    payload = [{
        "operationName": "StreamMetadata",
        "variables": {"channelLogin": channel_login.lower()},
        "extensions": {
            "persistedQuery": {"version": 1, "sha256Hash": STREAM_METADATA_HASH}
        },
    }]

    headers = {
        "Client-Id": FRONTEND_CLIENT_ID,
        "Content-Type": "application/json",
        "Origin": "https://www.twitch.tv",
        "Referer": f"https://www.twitch.tv/{channel_login}",
        "User-Agent": "Mozilla/5.0 (compatible; twitch-unofficial-checker/1.0)",
    }

    async with session.post(GQL_URL, headers=headers, data=json.dumps(payload)) as resp:
        text = await resp.text()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            # Nie parsuje się -> traktuj jako offline/błąd
            return False

        reply = parsed[0] if isinstance(parsed, list) and parsed else parsed
        data = reply.get("data", {}) if isinstance(reply, dict) else {}

        # szukamy info o streamie w kilku miejscach
        maybe_stream = (
            data.get("stream")
            or data.get("user", {}).get("stream")
            or data.get("channel", {}).get("stream")
            or data
        )

        is_live = False
        if isinstance(maybe_stream, dict):
            if maybe_stream.get("type") == "live":
                is_live = True
            elif maybe_stream.get("isLive") is True or maybe_stream.get("is_live") is True:
                is_live = True
            elif str(maybe_stream.get("status", "")).lower() == "live":
                is_live = True
            elif maybe_stream.get("id") or maybe_stream.get("startedAt"):
                # heurystyka
                is_live = True

        return bool(is_live)

# --- GŁÓWNA PĘTLA (drop-in zamiast decapi) ---
async def vedal_watch_loop(client_ref, startup_time: datetime):
    print("🚀 Vedal watch loop started")
    session_timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=session_timeout) as session:
        while client_ref.vedal_loop:
            now = datetime.now()

            if should_skip_today(startup_time, now):
                sleep_s = seconds_until_next_day_window(now)
                await asyncio.sleep(sleep_s)
                continue

            if client_ref.already_notified_today:
                sleep_s = seconds_until_next_day_window(now)
                client_ref.already_notified_today = False
                await asyncio.sleep(sleep_s)
                continue

            if not in_time_window(now):
                sleep_s = seconds_until_next_window(now)
                await asyncio.sleep(sleep_s)
                continue

            # --- tu sprawdzamy LIVE przez GraphQL zamiast decapi ---
            try:
                print(f"[{now:%H:%M:%S}] 🔎 Checking live -> {CHANNEL_LOGIN}")
                live = await is_live_unofficial(session, CHANNEL_LOGIN)

                if live:
                    print(f"[{now:%H:%M:%S}] 🎉 {CHANNEL_LOGIN} is LIVE!")
                    environment = os.getenv("ENVIRONMENT")
                    if environment == "production":
                        await client_ref.send_discord_message(f"https://www.twitch.tv/{CHANNEL_LOGIN}", client_ref.target_user_id)
                    else:
                        await client_ref.send_channel_message(client_ref.debug_channel_id, f"https://www.twitch.tv/{CHANNEL_LOGIN}")
                    client_ref.already_notified_today = True
                    continue
                else:
                    print(f"[{now:%H:%M:%S}] ❄ still offline")

            except Exception as e:
                print(f"[{now:%H:%M:%S}] 💀 request error: {e}")

            delay = calc_sleep_seconds(datetime.now())
            print(f"[{datetime.now():%H:%M:%S}] waiting {delay}s until the next check\n")
            await asyncio.sleep(delay)
