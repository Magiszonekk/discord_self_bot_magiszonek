import discord
import asyncio
import os
from logging_utils import log


class DiscordActions:
    """
    Manages Discord connections on-demand.
    Connects only when needed, performs action, then disconnects.
    """

    def __init__(self):
        self.token = os.getenv("TOKEN")
        self.client = None
        self.is_connected = False
        self._lock = asyncio.Lock()
        self._ready_event = asyncio.Event()

    async def _ensure_connected(self):
        """Ensures we're connected to Discord. Connects if not."""
        async with self._lock:
            if self.is_connected and self.client and not self.client.is_closed():
                return True

            self._ready_event.clear()
            self.client = discord.Client(self_bot=True)

            @self.client.event
            async def on_ready():
                log(f"Discord connected as {self.client.user}", True)
                self.is_connected = True
                self._ready_event.set()

            # Start client in background
            asyncio.create_task(self._run_client())

            # Wait for ready with timeout
            try:
                await asyncio.wait_for(self._ready_event.wait(), timeout=30)
                return True
            except asyncio.TimeoutError:
                log("Discord connection timeout", True, "error")
                await self._disconnect_internal()
                return False

    async def _run_client(self):
        """Runs the Discord client."""
        try:
            await self.client.start(self.token)
        except Exception as e:
            log(f"Discord client error: {e}", True, "error")
            self.is_connected = False

    async def _disconnect_internal(self):
        """Internal disconnect without lock."""
        if self.client and not self.client.is_closed():
            await self.client.close()
        self.is_connected = False
        self.client = None

    async def disconnect(self):
        """Disconnects from Discord."""
        async with self._lock:
            await self._disconnect_internal()
            log("Discord disconnected", True)

    async def change_status(self, status_text: str) -> bool:
        """
        Connects to Discord, changes status, then disconnects.
        Returns True on success, False on failure.
        """
        try:
            if not await self._ensure_connected():
                return False

            activity = discord.CustomActivity(status_text)
            await self.client.change_presence(
                status=discord.Status.online,
                activity=activity,
                edit_settings=True
            )
            log(f"Status changed to: {status_text}", True)

            # Give Discord time to process the change
            await asyncio.sleep(2)

            await self.disconnect()
            return True

        except Exception as e:
            log(f"Error changing status: {e}", True, "error")
            await self.disconnect()
            return False

    async def send_dm(self, user_id: int, message: str) -> bool:
        """
        Connects to Discord, sends a DM, then disconnects.
        Returns True on success, False on failure.
        """
        try:
            if not await self._ensure_connected():
                return False

            user = self.client.get_user(user_id)
            if user is None:
                try:
                    user = await self.client.fetch_user(user_id)
                except Exception as e:
                    log(f"Cannot fetch user {user_id}: {e}", True, "error")
                    await self.disconnect()
                    return False

            await user.send(message)
            log(f"DM sent to {user_id}: {message}", True)

            await asyncio.sleep(1)
            await self.disconnect()
            return True

        except Exception as e:
            log(f"Error sending DM: {e}", True, "error")
            await self.disconnect()
            return False

    async def send_channel_message(self, channel_id: int, message: str) -> bool:
        """
        Connects to Discord, sends message to channel, then disconnects.
        Returns True on success, False on failure.
        """
        try:
            if not await self._ensure_connected():
                return False

            channel = self.client.get_channel(channel_id)
            if channel is None:
                try:
                    channel = await self.client.fetch_channel(channel_id)
                except Exception as e:
                    log(f"Cannot fetch channel {channel_id}: {e}", True, "error")
                    await self.disconnect()
                    return False

            await channel.send(message)
            log(f"Message sent to channel {channel_id}: {message}", True)

            await asyncio.sleep(1)
            await self.disconnect()
            return True

        except Exception as e:
            log(f"Error sending channel message: {e}", True, "error")
            await self.disconnect()
            return False


# Global instance
_discord_actions = None


def get_discord_actions() -> DiscordActions:
    """Returns singleton instance of DiscordActions."""
    global _discord_actions
    if _discord_actions is None:
        _discord_actions = DiscordActions()
    return _discord_actions
