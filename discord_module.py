from email import message
import discord
import asyncio
import random
import os
from datetime import datetime
from db_utils import (
    add_status_request, get_added_statuses_from_user,
    get_all_permissions, approve_status_by_value, get_approved_statuses,
    get_status_by_category_and_user, get_statuses_by_category, get_all_categories,
    remove_status, remove_category, add_category, does_status_exist, get_all_permissions,
    add_permission, remove_permission
)
from is_live import test_eventsub
from dotenv import load_dotenv
import re
from logging_utils import log
from logging_utils import logs_message_handler

load_dotenv()

class MyClient(discord.Client):
    def __init__(self):
        # self_bot=True is required for discord.py-self
        super().__init__(self_bot=True)

        self.target_user_id = int(os.getenv("BROADCAST_NOTIFY_USER_ID"))  # <- id for Vedal987 notifications
        self.debug_channel_id = int(os.getenv("DEBUG_CHANNEL_ID"))  # <- channel id for debug messages
        self.already_notified_today = False
        self.bg_tasks_started = False
        self.status_rotation_interval = {"min": 25, "max": 45}  # random timeout for status in minutes
        self.users_with_permissions = get_all_permissions()
        self.discord_message_length_limit = 2000
        self.statuses = get_approved_statuses()
        self.rotate_status = True
        self.vedal_loop = True
        self.command_list = [
            "!help",
            "!ping",
            "!change_status",
            "!my_status_list",
            "!my_status_list",
            "!add_status",
            "!remove_status",
            "!status_list",
            "!category_list",
            "!add_category",
            "!remove_category",
            "!permissions_list",
            "!add_permission",
            "!remove_permission",
            "!rotate_status",
            "!vedal_loop",
        ]

    def log_command_usage(self, command_name: str, author, success: bool, detail: str = "") -> None:
        """
        Helper for consistent command logging.
        """
        user_display = f"{author} ({getattr(author, 'id', 'unknown')})"
        outcome = "SUCCESS" if success else "FAILED"
        suffix = f" | {detail}" if detail else ""
        log(f"[COMMAND] {command_name} by {user_display}: {outcome}{suffix}", True)

    async def on_ready(self):
        print("Logged on as", self.user)
        if not self.bg_tasks_started:
            self.bg_tasks_started = True
            asyncio.create_task(self.rotate_status_task())
            try:
                asyncio.create_task(
                    test_eventsub(
                        os.getenv("BOT_CLIENT_ID"),
                        os.getenv("BOT_ACCESS_TOKEN"),
                        self
                    )
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
        permitted_user_ids = [self.user.id, *[u["user_id"] for u in self.users_with_permissions]]

        # ignore messages from people without permissions
        if message.author.id not in permitted_user_ids:
            if content.startswith(tuple(self.command_list)):
                command_name = content.split()[0]
                self.log_command_usage(command_name, message.author, False, "Insufficient permissions")
            return
            
        # for debugging purposes
        # if message.author.id == self.user.id:
        # print(f"Message from {message.author} ({message.author.id}): {message.content}")

        if content == "!ping":
            command_name = "!ping"
            try:
                await message.channel.send("pong")
                self.log_command_usage(command_name, message.author, True)
            except Exception as e:
                self.log_command_usage(command_name, message.author, False, f"error={e}")
            return

        if content == "!change_status":
            command_name = "!change_status"
            new_status = random.choice(self.statuses)
            print(f"[{datetime.now():%H:%M}] Manual status change to: {new_status['status']}")

            try:
                await self.change_presence(
                    activity=discord.CustomActivity(new_status['status']),
                    status=discord.Status.online,
                    edit_settings=True
                )
                await message.add_reaction("✅")
                self.log_command_usage(command_name, message.author, True, f"status='{new_status['status']}'")
            except Exception as e:
                print("change_presence error (manual):", e)
                await message.add_reaction("❌")
                self.log_command_usage(command_name, message.author, False, f"error={e}")
            return

        if content == "!my_status_list":
            command_name = "!my_status_list"
            user_statuses = get_added_statuses_from_user(message.author.id)
            detail = ""

            if user_statuses:
                status_list = "\n".join(
                    f"- ({s['id']}) **{s['status']}** {'✅' if s['approved_by_user_id'] else '❌'}"
                    for s in user_statuses
                )

                if len(status_list) > self.discord_message_length_limit:
                    status_list_categories = {s['category'] for s in user_statuses}
                    await message.channel.send("## You have too many added statuses to display, but you can specify a particular category (!my_statuses category).\nHere are your options:")
                    await message.channel.send(", ".join(status_list_categories))
                    detail = f"{len(user_statuses)} statuses (truncated)"
                else:
                    await message.channel.send(f"## Your added statuses:\n{status_list}")
                    detail = f"{len(user_statuses)} statuses"
            else:
                await message.channel.send("## You haven't added any statuses yet.")
                detail = "no statuses"

            self.log_command_usage(command_name, message.author, True, detail)
            return

        if content.startswith("!my_status_list "):
            command_name = "!my_status_list"
            category = content[len("!my_status_list "):].strip()
            user_statuses = get_status_by_category_and_user(category, message.author.id)

            if user_statuses:
                status_list = "\n".join(
                    f"- ({s['id']}) **{s['status']}** {'✅' if s['approved_by_user_id'] else '❌'}"
                    for s in user_statuses
                )
                await message.channel.send(f"## Your added statuses in the '{category}' category:\n{status_list}")
                detail = f"{len(user_statuses)} statuses in {category}"
            else:
                await message.channel.send(f"## You haven't added any statuses in the '{category}' category yet.")
                detail = f"no statuses in {category}"

            self.log_command_usage(command_name, message.author, True, detail)
            return

        if content.startswith("!remove_status "):
            command_name = "!remove_status"
            status_to_remove = content[len("!remove_status "):].strip()
            user_statuses = get_added_statuses_from_user(message.author.id)
            user_status_values = [s['id'] for s in user_statuses]

            if status_to_remove not in user_status_values:
                await message.channel.send("## You can't remove a status you didn't add.")
                self.log_command_usage(command_name, message.author, False, f"id={status_to_remove} not owned")
                return

            remove_status(status_to_remove)
            await message.add_reaction("✅")
            self.log_command_usage(command_name, message.author, True, f"id={status_to_remove}")
            return

        if content.startswith("!add_status "):
            command_name = "!add_status"
            # remove the "!add_status " prefix
            raw_args = content[len("!add_status "):].strip()

            # split by spaces
            parts = raw_args.split()

            print(parts)

            # minimum two elements required: [category] [content...]
            if len(parts) < 2:
                await message.add_reaction("❌")
                await message.channel.send(
                    "Usage: `!add_status [category] status content`\n"
                    "Example: `!add_status general Hello world!`"
                )
                self.log_command_usage(command_name, message.author, False, "Missing category/content")
                return

            categories = get_all_categories()
            category = parts[0]

            if category not in [c['label'] for c in categories]:
                await message.add_reaction("❌")
                await message.channel.send(
                    f"Category '{category}' does not exist.\nAvailable categories:\n- "
                    + "\n- ".join(c['label'] for c in categories)
                )
                self.log_command_usage(command_name, message.author, False, f"Category '{category}' missing")
                return

            new_status = " ".join(parts[1:]).strip()

            if not new_status:
                await message.add_reaction("❌")
                await message.channel.send("Provide the status text after the category 🤨")
                self.log_command_usage(command_name, message.author, False, "Empty status content")
                return

            if does_status_exist(new_status):
                await message.add_reaction("❌")
                await message.channel.send("That status already exists")
                self.log_command_usage(command_name, message.author, False, "Status duplicate")
                return

            add_status_request(
                person_name=str(message.author),
                person_id=message.author.id,
                status=new_status,
                category=category
            )

            await message.add_reaction("✅")
            self.log_command_usage(command_name, message.author, True, f"category={category}")
            return

        if content.startswith("!status_list "):
            command_name = "!status_list"
            category = content[len("!status_list "):].strip()
            statuses_in_category = get_statuses_by_category(category)

            if statuses_in_category:
                status_list = "\n".join(
                    f"- **{s['status']}** ({s['person_name']})"
                    for s in statuses_in_category
                )

                if len(status_list) > self.discord_message_length_limit:
                    await message.channel.send("There are too many statuses in this category to display.")
                    detail = f"{len(statuses_in_category)} statuses (too long) in {category}"
                else:
                    await message.channel.send(f"## Statuses in the '{category}' category:\n{status_list}")
                    detail = f"{len(statuses_in_category)} statuses in {category}"
            else:
                await message.channel.send(f"## No statuses in the '{category}' category.")
                detail = f"0 statuses in {category}"

            self.log_command_usage(command_name, message.author, True, detail)
            return

        if content == "!category_list":
            command_name = "!category_list"
            categories = get_all_categories()
            category_list = "\n- ".join(c['label'] for c in categories)
            category_list = "- " + category_list if category_list else "No categories defined."
            await message.channel.send(f"## Available status categories:\n{category_list}")
            self.log_command_usage(command_name, message.author, True, f"{len(categories)} categories")
            return

        if content.startswith("!add_category "):
            command_name = "!add_category"
            new_category = content[len("!add_category "):].strip()

            if " " in new_category:
                await message.channel.send("The category name cannot contain spaces.")
                self.log_command_usage(command_name, message.author, False, "Contains spaces")
                return

            if new_category:
                add_category(
                    created_by_user_id=message.author.id,
                    label=new_category
                )
                await message.add_reaction("✅")
                self.log_command_usage(command_name, message.author, True, f"category={new_category}")
            else:
                await message.channel.send("You didn't provide a category name to add.")
                self.log_command_usage(command_name, message.author, False, "Missing category name")
            return

        if content.startswith("!remove_category "):
            command_name = "!remove_category"
            categories = get_all_categories()
            categories_labels = [c['label'] for c in categories]
            category_to_remove = content[len("!remove_category "):].strip()
            if category_to_remove:
                if category_to_remove in categories_labels:
                    created_by_user_id = next(c['created_by_user_id'] for c in categories if c['label'] == category_to_remove)
                    if created_by_user_id != message.author.id:
                        await message.channel.send("You can only delete categories that you added yourself.")
                        self.log_command_usage(command_name, message.author, False, f"{category_to_remove} owned by another user")
                        return
                    remove_category(category_to_remove)
                    await message.add_reaction("✅")
                    self.log_command_usage(command_name, message.author, True, f"category={category_to_remove}")
                else:
                    await message.channel.send(f"Category not found: {category_to_remove}")
                    self.log_command_usage(command_name, message.author, False, f"{category_to_remove} missing")
            else:
                await message.channel.send("You didn't provide a category name to remove.")
                self.log_command_usage(command_name, message.author, False, "Missing category name")
            return

        if content == "!permissions_list":
            command_name = "!permissions_list"
            if message.author.id != self.user.id:
                self.log_command_usage(command_name, message.author, False, "Admin only")
                return
            permissions = get_all_permissions()
            permission_list = "\n".join(
                f"- User ID: **{p['user_id']}**, Label: **{p['label']}**"
                for p in permissions
            )
            await message.channel.send(f"## List of users with permissions:\n{permission_list}")
            self.log_command_usage(command_name, message.author, True, f"{len(permissions)} entries")
            return

        if content.startswith("!add_permission "):
            command_name = "!add_permission"
            if message.author.id != self.user.id:
                self.log_command_usage(command_name, message.author, False, "Admin only")
                return
            parts = content[len("!add_permission "):].strip().split()
            if len(parts) < 2:
                await message.channel.send("Usage: `!add_permission <user_id> <label>`")
                self.log_command_usage(command_name, message.author, False, "Missing args")
                return

            try:
                user_id = int(parts[0])
            except ValueError:
                await message.channel.send("Invalid user_id. It must be a number.")
                self.log_command_usage(command_name, message.author, False, "Invalid user_id")
                return

            label = " ".join(parts[1:]).strip()
            add_permission(user_id, label)
            await message.add_reaction("✅")
            self.log_command_usage(command_name, message.author, True, f"user_id={user_id}")
            return

        if content.startswith("!remove_permission "):
            command_name = "!remove_permission"
            if message.author.id != self.user.id:
                self.log_command_usage(command_name, message.author, False, "Admin only")
                return
            parts = content[len("!remove_permission "):].strip().split()
            if len(parts) < 1:
                await message.channel.send("Usage: `!remove_permission <user_id>`")
                self.log_command_usage(command_name, message.author, False, "Missing user_id")
                return

            try:
                user_id = int(parts[0])
            except ValueError:
                await message.channel.send("Invalid user_id. It must be a number.")
                self.log_command_usage(command_name, message.author, False, "Invalid user_id")
                return

            remove_permission(user_id)
            await message.add_reaction("✅")
            self.log_command_usage(command_name, message.author, True, f"user_id={user_id}")
            return

        if content == "!rotate_status":
            command_name = "!rotate_status"
            if message.author.id != self.user.id:
                self.log_command_usage(command_name, message.author, False, "Admin only")
                return
            self.rotate_status = not self.rotate_status
            status_text = "enabled" if self.rotate_status else "disabled"
            await message.channel.send(f"Automatic status rotation is now {status_text}.")
            self.log_command_usage(command_name, message.author, True, status_text)
            return

        if content == "!vedal_loop":
            command_name = "!vedal_loop"
            if message.author.id != self.user.id:
                self.log_command_usage(command_name, message.author, False, "Admin only")
                return
            self.vedal_loop = not self.vedal_loop
            status_text = "enabled" if self.vedal_loop else "disabled"
            await message.channel.send(f"Vedal watch loop is now {status_text}.")
            self.log_command_usage(command_name, message.author, True, status_text)
            return

        if content == "!help":
            command_name = "!help"
            help_text = (
                "# Commands list:\n"
                "## General:\n"
                "- **!help**: Shows this help message\n"
                "- **!ping**: Responds with 'pong'\n"
                "- **!change_status**: Immediately changes the status to a random approved one\n\n"

                "## Statuses:\n"
                "- **!status_list <category>**: Shows the list of statuses in the specified category\n\n"
                "- **!my_status_list**: Shows the statuses you submitted\n"
                "- **!my_status_list <category>**: Shows the statuses you submitted in the specified category\n\n"
                "- **!add_status <category> <status>**: Adds a new status to the suggestion pool\n"
                "- **!remove_status <id>**: Removes a status from the suggestion pool\n"

                "## Categories:\n"
                "- **!category_list**: Shows the list of available status categories\n"
                "- **!add_category <name>**: Adds a new status category\n"
                "- **!remove_category <name>**: Removes a status category (if you added it)\n"

                "## URL:\n"
                "- [github repo](https://github.com/Magiszonekk/discord_self_bot_magiszonek)"
            )
            await message.channel.send(help_text, suppress_embeds=True)
            self.log_command_usage(command_name, message.author, True)
            return

        if content == "!help 2":
            command_name = "!help 2"
            help_text = (
                "# Admin commands:\n"
                "## General:\n"
                "- **!rotate_status**: Enables/disables automatic status rotation\n"
                "- **!vedal_loop**: Enables/disables the loop that checks whether Vedal is online\n\n"

                "## Permissions:\n"
                "- **!permissions_list**: Shows the list of users with permissions\n"
                "- **!add_permission <user_id> <label>**: Adds a permission for a user\n"
                "- **!remove_permission <user_id>**: Removes a user's permission\n\n"

                "## Logs:\n"
                "- **!logs**: Shows the last 10 lines of the log file\n"
                "- **!logs <day> <month> <hour> <minute> [second]**: Shows 10 log lines closest to the specified date and time\n\n"

                "## URL:\n"
                "- [github repo](https://github.com/Magiszonekk/discord_self_bot_magiszonek)"
            )
            await message.channel.send(help_text, suppress_embeds=True)
            self.log_command_usage(command_name, message.author, True)
            return

        if content.startswith("!logs"):
            await logs_message_handler(message, self)
            return                
                
                
        if vedal_reaction(content) and message.author.id == self.target_user_id:
            await message.add_reaction("❤️")

    async def on_reaction_add(self, reaction, user):
        if user.id != self.user.id:
            return

        print(f"Reaction from {user}: {reaction.emoji} on message {reaction.message.id}")

        if str(reaction.emoji) == "👍":
            content = reaction.message.content

            if content.startswith("!add_status "):
                parts = content.split(maxsplit=2)
                print(len(parts))
                if len(parts) < 3:
                    await reaction.message.channel.send("❌ Brakuje kategorii lub statusu.")
                    return
                
                print(f"Parts: {parts}")
                category = parts[1].strip()
                status_value = parts[2].strip()

                approve_status_by_value(status_value, user.id)

                await reaction.message.channel.send(
                    f"👍 Status **'{status_value}'** z kategorii **'{category}'** został zatwierdzony przez {user}."
                )


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

def vedal_reaction(raw: str) -> bool:
    cleaned = parse_message_content(raw).lower()
    triggers = ["ty chuju", "ty huju"]
    return cleaned in triggers
