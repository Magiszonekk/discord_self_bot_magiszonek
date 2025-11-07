import asyncio
import aiohttp
import json
import requests
import os

async def test_eventsub(CLIENT_ID: str, USER_TOKEN: str, client_ref):
    """Minimal test - just prints when Vedal goes live"""
    
    BROADCASTER_ID = get_twitch_user_id(os.getenv("BROADCASTER"))

    # Connect to WebSocket
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect("wss://eventsub.wss.twitch.tv/ws") as ws:
            print("🔌 Connected! Waiting for messages...")
            
            async for msg in ws:
                data = json.loads(msg.data)
                msg_type = data["metadata"]["message_type"]
                
                if msg_type == "session_welcome":
                    # Got session ID - now subscribe
                    session_id = data["payload"]["session"]["id"]
                    print(f"✅ Session ID: {session_id}")
                    
                    # Subscribe to stream.online
                    sub_url = "https://api.twitch.tv/helix/eventsub/subscriptions"
                    headers = {
                        "Client-Id": CLIENT_ID,
                        "Authorization": f"Bearer {USER_TOKEN}",
                        "Content-Type": "application/json"
                    }
                    payload = {
                        "type": "stream.online",
                        "version": "1",
                        "condition": {"broadcaster_user_id": BROADCASTER_ID},
                        "transport": {"method": "websocket", "session_id": session_id}
                    }
                    
                    async with session.post(sub_url, headers=headers, json=payload) as resp:
                        if resp.status == 202:
                            print(f"🎯 Subscribed! Waiting for {os.getenv('BROADCASTER')} to go live...")
                        else:
                            print(f"❌ Failed: {await resp.text()}")
                
                elif msg_type == "notification":
                    # STREAM WENT LIVE!
                    event = data["payload"]["event"]
                    print(f"🚀 {os.getenv('BROADCASTER')} is LIVE!")
                    client_ref.send_discord_message(f"https://www.twitch.tv/{event['broadcaster_user_login']}",client_ref.target_user_id)

                # elif msg_type == "session_keepalive":
                    # print("💓 (keepalive)")

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
        print("User not found!")
        return None