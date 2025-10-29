import asyncio
import aiohttp
from datetime import datetime, timedelta

URL = "https://decapi.me/twitch/uptime/vedal987"

START_HOUR = 20
END_HOUR = 22

PHASE1_END = 15   # do 20:15 -> co 1 min
PHASE2_END = 30   # do 20:30 -> co 2 min
# potem -> co 5 min

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
    # jutro o 20:00
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
        # przed 20:00 -> do dzisiaj 20:00
        return int((today_start - now).total_seconds())
    elif now >= today_end:
        # po 22:00 -> jutro 20:00
        return seconds_until_next_day_window(now)
    else:
        # w środku okna nie powinniśmy tu trafić
        return 0

async def vedal_watch_loop(client_ref, startup_time: datetime):
    """
    client_ref = instancja MyClient (Discord client),
    używana do wysłania powiadomienia raz dziennie.
    """
    session_timeout = aiohttp.ClientTimeout(total=10)

    async with aiohttp.ClientSession(timeout=session_timeout) as session:
        while True:
            now = datetime.now()

            if should_skip_today(startup_time, now):
                sleep_s = seconds_until_next_day_window(now)
                # print(f"[{now:%H:%M:%S}] 🚫 Start dziś po 20:00, pomijam. Śpię {sleep_s}s do jutra 20:00")
                await asyncio.sleep(sleep_s)
                continue

            # jeśli już wysłaliśmy dzisiaj info -> śpimy do jutra 20:00
            if client_ref.already_notified_today:
                sleep_s = seconds_until_next_day_window(now)
                # print(f"[{now:%H:%M:%S}] ✅ Już zgłoszone dziś. Śpię {sleep_s}s do jutra 20:00")
                client_ref.already_notified_today = False  # zresetujemy dopiero po sleepie
                await asyncio.sleep(sleep_s)
                continue

            # jeśli nie jesteśmy w oknie 20-22 -> śpij do startu okna
            if not in_time_window(now):
                sleep_s = seconds_until_next_window(now)
                # print(f"[{now:%H:%M:%S}] Poza oknem. Śpię {sleep_s}s do kolejnego okna.")
                await asyncio.sleep(sleep_s)
                continue

            # jesteśmy w oknie -> sprawdzaj
            try:
                print(f"[{now:%H:%M:%S}] 🔎 Request -> {URL}")
                async with session.get(URL) as resp:
                    body = (await resp.text()).lower()

                if "offline" not in body:
                    # Vedal jest live -> wyślij DM raz
                    print(f"[{now:%H:%M:%S}] 🎉 Vedal is live!")
                    await client_ref.send_discord_message("https://www.twitch.tv/vedal987")
                    client_ref.already_notified_today = True
                    # i w następnej iteracji pętli pójdziemy spać do jutra
                    continue
                else:
                    print(f"[{now:%H:%M:%S}] ❄ dalej offline")

            except Exception as e:
                print(f"[{now:%H:%M:%S}] 💀 request error: {e}")

            delay = calc_sleep_seconds(datetime.now())
            print(f"[{datetime.now():%H:%M:%S}] czekam {delay}s do kolejnego checka\n")
            await asyncio.sleep(delay)

def should_skip_today(startup_time: datetime, now: datetime) -> bool:
    """
    Zwraca True jeśli:
    - bot wystartował dzisiaj
    - i wystartował PO 20:00
    czyli wtedy nie chcemy robić requestów dzisiaj.
    Jutro -> już normalnie.
    """
    same_day = (startup_time.date() == now.date())
    started_after_20 = startup_time.hour >= START_HOUR
    return same_day and started_after_20