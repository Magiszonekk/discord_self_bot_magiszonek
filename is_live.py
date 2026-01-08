import asyncio
import aiohttp
import json
import os
from logging_utils import log
from token_manager import get_token_manager, TwitchTokenManager
from discord_actions import get_discord_actions

BASE_WS_URL = "wss://eventsub.wss.twitch.tv/ws"

# Global state for controlling EventSub
_eventsub_running = False
_eventsub_should_stop = False


async def start_eventsub():
    """
    Starts the EventSub WebSocket listener.
    This runs in the background and sends Discord notifications when broadcaster goes live.
    """
    global _eventsub_running, _eventsub_should_stop

    if _eventsub_running:
        log("[EventSub] Already running", True, "warning")
        return

    _eventsub_running = True
    _eventsub_should_stop = False

    token_manager = get_token_manager()
    discord_actions = get_discord_actions()
    target_user_id = int(os.getenv("BROADCAST_NOTIFY_USER_ID", "0"))

    broadcaster_login = os.getenv("BROADCASTER")
    BROADCASTER_ID = await get_twitch_user_id(broadcaster_login, token_manager)
    log(f"[EventSub] BROADCASTER = {broadcaster_login}, ID = {BROADCASTER_ID}", True)

    if not BROADCASTER_ID:
        log("[EventSub] Failed to get BROADCASTER_ID - stopping", True, "error")
        _eventsub_running = False
        return

    current_url = BASE_WS_URL
    use_reconnect_once = False
    RECEIVE_TIMEOUT = 25

    try:
        async with aiohttp.ClientSession() as session:
            while not _eventsub_should_stop:
                log(f"[EventSub] Connecting to {current_url}", True)

                try:
                    async with session.ws_connect(current_url) as ws:
                        if use_reconnect_once:
                            current_url = BASE_WS_URL
                            use_reconnect_once = False

                        while not _eventsub_should_stop:
                            try:
                                msg = await asyncio.wait_for(
                                    ws.receive(),
                                    timeout=RECEIVE_TIMEOUT
                                )
                            except asyncio.TimeoutError:
                                log(
                                    f"[EventSub] No message for {RECEIVE_TIMEOUT}s - reconnecting",
                                    True,
                                    "warning",
                                )
                                await ws.close()
                                break

                            if msg.type == aiohttp.WSMsgType.TEXT:
                                try:
                                    data = json.loads(msg.data)
                                except json.JSONDecodeError:
                                    log(f"[EventSub] Non-JSON message: {msg.data!r}", True, "error")
                                    continue

                                metadata = data.get("metadata", {})
                                msg_type = metadata.get("message_type")

                                if msg_type == "session_keepalive":
                                    log(f"[EventSub] keepalive", False)

                                elif msg_type == "session_welcome":
                                    session_id = data["payload"]["session"]["id"]
                                    log(f"[EventSub] Session ID: {session_id}", True)

                                    sub_url = "https://api.twitch.tv/helix/eventsub/subscriptions"
                                    payload = {
                                        "type": "stream.online",
                                        "version": "1",
                                        "condition": {"broadcaster_user_id": BROADCASTER_ID},
                                        "transport": {
                                            "method": "websocket",
                                            "session_id": session_id,
                                        },
                                    }

                                    success = await _subscribe_with_retry(
                                        session, sub_url, payload, token_manager, broadcaster_login
                                    )

                                elif msg_type == "session_reconnect":
                                    reconnect_url = data["payload"]["session"]["reconnect_url"]
                                    log(f"[EventSub] Reconnect requested -> {reconnect_url}", True, "warning")

                                    current_url = reconnect_url
                                    use_reconnect_once = True
                                    await ws.close()
                                    break

                                elif msg_type == "notification":
                                    event = data["payload"]["event"]
                                    log(
                                        f"[EventSub] {event['broadcaster_user_login']} is LIVE!",
                                        True,
                                    )

                                    # Send Discord DM notification
                                    await discord_actions.send_dm(
                                        target_user_id,
                                        f"https://www.twitch.tv/{event['broadcaster_user_login']}"
                                    )

                                else:
                                    log(f"[EventSub] Unknown msg_type: {msg_type}", True)

                            elif msg.type == aiohttp.WSMsgType.ERROR:
                                log(f"[EventSub] WS error: {ws.exception()}", True, "error")
                                break
                            elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSING):
                                log(f"[EventSub] WS closed with code {ws.close_code}", True, "warning")
                                break

                    if not _eventsub_should_stop:
                        log("[EventSub] WS loop ended - reconnecting in 3s...", True, "warning")
                        await asyncio.sleep(3)

                except aiohttp.WSServerHandshakeError as e:
                    log(f"[EventSub] Handshake error: {repr(e)}", True, "error")

                    if e.status == 429:
                        log("[EventSub] Rate limited (429) - waiting 60s", True, "warning")
                        current_url = BASE_WS_URL
                        use_reconnect_once = False
                        await asyncio.sleep(60)
                    else:
                        await asyncio.sleep(5)

                except asyncio.CancelledError:
                    log("[EventSub] Cancelled", True)
                    break

                except Exception as e:
                    log(f"[EventSub] Loop crashed: {repr(e)} - reconnect in 5s", True, "error")
                    await asyncio.sleep(5)

    finally:
        _eventsub_running = False
        log("[EventSub] Stopped", True)


async def stop_eventsub():
    """Signals the EventSub loop to stop."""
    global _eventsub_should_stop
    _eventsub_should_stop = True
    log("[EventSub] Stop requested", True)


def is_eventsub_running() -> bool:
    """Returns whether EventSub is currently running."""
    return _eventsub_running


async def _subscribe_with_retry(session, sub_url, payload, token_manager, broadcaster_login):
    """
    Attempts to subscribe to EventSub. If 401 is received, refreshes token and retries.
    """
    for attempt in range(2):
        headers = {
            "Client-Id": token_manager.get_client_id(),
            "Authorization": f"Bearer {token_manager.get_token()}",
            "Content-Type": "application/json",
        }

        async with session.post(sub_url, headers=headers, json=payload) as resp:
            body = await resp.text()
            log(f"[EventSub] Sub response: {resp.status} {body}", True)

            if resp.status == 202:
                log(f"[EventSub] Subscribed! Waiting for {broadcaster_login} to go live...", True)
                return True
            elif resp.status == 401:
                log("[EventSub] Token expired (401), refreshing...", True, "warning")
                if token_manager.refresh():
                    log("[EventSub] Token refreshed, retrying subscription...", True)
                    continue
                else:
                    log("[EventSub] Failed to refresh token", True, "error")
                    return False
            else:
                log("[EventSub] Failed to subscribe", True, "error")
                return False

    return False


async def get_twitch_user_id(username, token_manager: TwitchTokenManager):
    """
    Fetches Twitch user ID by username. Handles 401 with token refresh.
    """
    url = f"https://api.twitch.tv/helix/users?login={username}"

    for attempt in range(2):
        headers = {
            "Client-Id": token_manager.get_client_id(),
            "Authorization": f"Bearer {token_manager.get_token()}",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 401:
                    log("[EventSub] Token expired (401) while fetching user_id, refreshing...", True, "warning")
                    if token_manager.refresh():
                        continue
                    else:
                        log("[EventSub] Failed to refresh token", True, "error")
                        return None

                data = await response.json()

                if data.get("data"):
                    user = data["data"][0]
                    return user["id"]
                else:
                    log("[EventSub] User not found!", True, "warning")
                    return None

    return None
