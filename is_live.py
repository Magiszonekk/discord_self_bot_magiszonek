import asyncio
import aiohttp
import json
import os
from logging_utils import log
import requests

BASE_WS_URL = "wss://eventsub.wss.twitch.tv/ws"

async def test_eventsub(CLIENT_ID: str, USER_TOKEN: str, client_ref):
    broadcaster_login = os.getenv("BROADCASTER")
    BROADCASTER_ID = get_twitch_user_id(broadcaster_login)
    log(f"BROADCASTER = {broadcaster_login}, ID = {BROADCASTER_ID}", True)

    if not BROADCASTER_ID:
        log("❌ Nie udało się pobrać BROADCASTER_ID – przerywam.", True, "error")
        return

    current_url = BASE_WS_URL
    use_reconnect_once = False  # flaga czy następne połączenie ma użyć reconnect_url

    async with aiohttp.ClientSession() as session:
        while True:
            log(f"🔌 Connecting to {current_url}", True)

            try:
                async with session.ws_connect(current_url) as ws:
                    # jeśli użyliśmy reconnect_url -> po udanym handshake
                    # wracamy do BASE_WS_URL na przyszłość
                    if use_reconnect_once:
                        current_url = BASE_WS_URL
                        use_reconnect_once = False

                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            try:
                                data = json.loads(msg.data)
                            except json.JSONDecodeError:
                                log(f"⚠️ Non-JSON message: {msg.data!r}", True, "error")
                                continue

                            metadata = data.get("metadata", {})
                            msg_type = metadata.get("message_type")

                            if msg_type == "session_keepalive":
                                log(f"📨 message_type = {msg_type}", False)
                                log("💓 keepalive", False)

                            elif msg_type == "session_welcome":
                                session_id = data["payload"]["session"]["id"]
                                log(f"✅ Session ID: {session_id}", True)

                                # SUBSKRYBUJEMY TYLKO PRZY PIERWSZYM WELCOME DLA SESJI
                                # (opcjonalnie możesz tu dodać jakąś ochronę przed duplikatami)
                                sub_url = "https://api.twitch.tv/helix/eventsub/subscriptions"
                                headers = {
                                    "Client-Id": CLIENT_ID,
                                    "Authorization": f"Bearer {USER_TOKEN}",
                                    "Content-Type": "application/json",
                                }
                                payload = {
                                    "type": "stream.online",
                                    "version": "1",
                                    "condition": {"broadcaster_user_id": BROADCASTER_ID},
                                    "transport": {
                                        "method": "websocket",
                                        "session_id": session_id,
                                    },
                                }

                                async with session.post(sub_url, headers=headers, json=payload) as resp:
                                    body = await resp.text()
                                    log(f"📤 sub response: {resp.status} {body}", True)

                                    if resp.status == 202:
                                        log(
                                            f"🎯 Subscribed! Waiting for {broadcaster_login} to go live...",
                                            True,
                                        )
                                    else:
                                        log("❌ Failed to subscribe", True, "error")

                            elif msg_type == "session_reconnect":
                                reconnect_url = data["payload"]["session"]["reconnect_url"]
                                log(f"🔁 session_reconnect -> {reconnect_url}", True, "warning")

                                # UŻYJ reconnect_url TYLKO RAZ
                                current_url = reconnect_url
                                use_reconnect_once = True
                                break  # przerwij pętlę WS, przejdź do kolejnego while True (nowe połączenie)

                            elif msg_type == "notification":
                                event = data["payload"]["event"]
                                log(
                                    f"🚀 {event['broadcaster_user_login']} is LIVE! type={event['type']}",
                                    True,
                                )

                                await client_ref.send_discord_message(
                                    f"https://www.twitch.tv/{event['broadcaster_user_login']}",
                                    int(client_ref.target_user_id),
                                )
                                # jeśli async:
                                # await client_ref.send_discord_message(...)

                            else:
                                log(f"🤔 unknown msg_type: {msg_type}", True)

                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            log(f"💥 WS error: {ws.exception()}", True, "error")
                            break
                        elif msg.type == aiohttp.WSMsgType.CLOSED:
                            log(f"🔌 WS closed with code {ws.close_code}", True, "warning")
                            break

                log("⚠️ WS loop ended – reconnecting in 3s...", True, "warning")
                await asyncio.sleep(3)

            except aiohttp.WSServerHandshakeError as e:
                # tu widzisz 429
                log(f"💣 Handshake error: {repr(e)}", True, "error")

                if e.status == 429:
                    # za dużo prób / reconnect_url martwy -> odpuść ten URL
                    log("⏳ 429 from Twitch – odczekuję 60s i wracam do BASE_WS_URL", True, "warning")
                    current_url = BASE_WS_URL
                    use_reconnect_once = False
                    await asyncio.sleep(60)
                else:
                    await asyncio.sleep(5)

            except Exception as e:
                log(f"💣 EventSub loop crashed: {repr(e)} – reconnect in 5s", True, "error")
                await asyncio.sleep(5)


def get_twitch_user_id(username):
    url = f"https://api.twitch.tv/helix/users?login={username}"
    headers = {
        "Client-Id": os.getenv("BOT_CLIENT_ID"),  # public client
        "Authorization": "Bearer " + os.getenv("BOT_ACCESS_TOKEN")  # or use your token
    }
    
    response = requests.get(url, headers=headers)
    data = response.json()
    
    if data.get("data"):
        user = data["data"][0]
        return user["id"]
    else:
        log("User not found!", True, "warning")
        return None
