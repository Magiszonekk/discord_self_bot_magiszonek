import discord
import asyncio
import random
import os
from db_utils import get_approved_statuses
from is_live import test_eventsub
from token_manager import get_token_manager
from dotenv import load_dotenv
import re
from logging_utils import log

load_dotenv()

class MyClient(discord.Client):
    def __init__(self):
        # self_bot=True is required for discord.py-self
        super().__init__(self_bot=True)

        self.target_user_id = int(os.getenv("BROADCAST_NOTIFY_USER_ID"))  # <- id for streamer notifications
        self.debug_channel_id = int(os.getenv("DEBUG_CHANNEL_ID"))  # <- channel id for debug messages
        self.already_notified_today = False
        self.bg_tasks_started = False
        self.status_rotation_interval = {"min": 25, "max": 45}  # random timeout for status in minutes
        self.statuses = get_approved_statuses()
        self.rotate_status = True
        self.streamer_loop = True

    async def on_ready(self):
        print("Logged on as", self.user)
        if not self.bg_tasks_started:
            self.bg_tasks_started = True
            asyncio.create_task(self.rotate_status_task())
            try:
                token_manager = get_token_manager()
                asyncio.create_task(
                    test_eventsub(token_manager, self)
                )
                print("✅ EventSub task started")
            except Exception as e:
                print(f"❌ EventSub failed: {e}")

    async def rotate_status_task(self):
        while self.rotate_status:
            try:
                activity = discord.CustomActivity(random.choice(self.statuses)['status'])
                await self.change_presence(
                    status=discord.Status.online,
                    activity=activity,
                    edit_settings=True
                )
            except Exception as e:
                print("change_presence error (rotate):", e)

            sleep_minutes = random.randint(self.status_rotation_interval['min'], self.status_rotation_interval['max'])
            sleep_seconds = sleep_minutes * 60
            await asyncio.sleep(sleep_seconds)

    async def on_message(self, message):
        content = message.content.strip()

        # React to messages from tracked user
        if keyword_reaction(content) and message.author.id == self.target_user_id:
            await message.add_reaction("❤️")

    async def send_discord_message(self, message: str, user_id: int):
        user = self.get_user(user_id)
        if user is None:
            try:
                user = await self.fetch_user(user_id)
            except Exception as e:
                log(f"Cannot fetch user {user_id}: {e}", True, "ERROR")
                return

        try:
            await user.send(message)
            log(f"✅ Sent DM to {user_id}: {message}", True)
        except Exception as e:
            log(f"❌ Failed to send DM to {user_id}: {e}", True, "ERROR")

    async def send_channel_message(self, channel_id: int, message: str):
        channel = self.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.fetch_channel(channel_id)
            except Exception as e:
                log(f"Cannot fetch channel {channel_id}: {e}", True, "ERROR")
                return

        try:
            await channel.send(message)
            log(f"✅ Sent channel message to {channel_id}: {message}", True)
        except Exception as e:
            log(f"❌ Failed to send channel message to {channel_id}: {e}", True, "ERROR")

def parse_message_content(raw: str) -> str:
    cleaned = re.sub(r'[^a-zA-Z0-9 ]', '', raw)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned

def keyword_reaction(raw: str) -> bool:
    cleaned = parse_message_content(raw).lower()
    triggers = ["ty chuju", "ty huju"]
    return cleaned in triggers
