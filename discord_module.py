import discord
import asyncio
import random
from datetime import datetime, timedelta
from db_utils import (
    get_all_statuses, add_status_request, get_added_statuses_from_user,
    get_all_permissions, approve_status_by_value, get_approved_statuses,
    get_status_by_category_and_user, get_statuses_by_category, get_all_categories,
    remove_status, remove_category, add_category, does_status_exist, get_all_permissions,
    add_permission, remove_permission
)
import os

class MyClient(discord.Client):
    def __init__(self):
        # self_bot=True is required for discord.py-self
        super().__init__(self_bot=True)

        self.target_user_id = 427698599179059202  # <- id for Vedal987 notifications
        self.already_notified_today = False
        self.bg_tasks_started = False
        self.status_rotation_interval = {"min": 25, "max": 45}  # random timeout for status in minutes
        self.users_with_permissions = get_all_permissions()
        self.discord_message_length_limit = 2000
        self.statuses = get_approved_statuses()
        self.rotate_status = True
        self.vedal_loop = True

    async def on_ready(self):
        print("Logged on as", self.user)

        if not self.bg_tasks_started:
            self.bg_tasks_started = True
            asyncio.create_task(self.rotate_status_task())
            # asyncio.create_task(self.daily_status_task())
            # vedal_watch_loop is started from main.py

    async def daily_status_task(self):
        while True:
            now = datetime.now()
            target = now.replace(hour=8, minute=0, second=0, microsecond=0)

            if now >= target:
                target += timedelta(days=1)

            wait_seconds = (target - now).total_seconds()
            print(f"Waiting {wait_seconds/3600:.2f}h until 8:00...")

            await asyncio.sleep(wait_seconds)

            new_status = random.choice(self.statuses)
            print(f"[{datetime.now():%H:%M}] Changing status to: {new_status['status']}")

            try:
                await self.change_presence(
                    activity=discord.CustomActivity(new_status['status']),
                    status=discord.Status.online,
                    edit_settings=True
                )
            except Exception as e:
                print("change_presence error (daily):", e)

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
        # ignore messages from people without permissions
        if message.author.id not in [self.user.id, *[u["user_id"] for u in self.users_with_permissions]]:
            return
            
        # for debugging purposes
        # if message.author.id == self.user.id:
        print(f"Message from {message.author} ({message.author.id}): {message.content}")

        if message.content == "!ping":
            await message.channel.send("pong")

        if message.content == "!change_status":
            new_status = random.choice(self.statuses)
            print(f"[{datetime.now():%H:%M}] Manual status change to: {new_status['status']}")

            try:
                await self.change_presence(
                    activity=discord.CustomActivity(new_status['status']),
                    status=discord.Status.online,
                    edit_settings=True
                )
                await message.add_reaction("✅")
            except Exception as e:
                print("change_presence error (manual):", e)
                await message.add_reaction("❌")

        if message.content == "!my_status_list":
            user_statuses = get_added_statuses_from_user(message.author.id)

            if user_statuses:
                status_list = "\n".join(
                    f"- ({s['id']}) **{s['status']}** {'✅' if s['approved_by_user_id'] else '❌'}"
                    for s in user_statuses
                )

                if len(status_list) > self.discord_message_length_limit:
                    status_list_categories = set()
                    for s in user_statuses:
                        category = s['category']
                        status_list_categories.add(category)
                    await message.channel.send("## You have too many added statuses to display, but you can specify a particular category (!my_statuses category).\nHere are your options:")
                    await message.channel.send(", ".join(status_list_categories))

                else:
                    print(status_list)
                    await message.channel.send(f"## Your added statuses:\n{status_list}")
            else:
                await message.channel.send("## You haven't added any statuses yet.")

        if message.content.startswith("!my_status_list "):
            category = message.content[len("!my_status_list "):].strip()
            user_statuses = get_status_by_category_and_user(category, message.author.id)

            if user_statuses:
                status_list = "\n".join(
                    f"- ({s['id']}) **{s['status']}** {'✅' if s['approved_by_user_id'] else '❌'}"
                    for s in user_statuses
                )
                await message.channel.send(f"## Your added statuses in the '{category}' category:\n{status_list}")
            else:
                await message.channel.send(f"## You haven't added any statuses in the '{category}' category yet.")

        if message.content.startswith("!remove_status "):
            status_to_remove = message.content[len("!remove_status "):].strip()
            user_statuses = get_added_statuses_from_user(message.author.id)
            user_status_values = [s['id'] for s in user_statuses]

            if status_to_remove not in user_status_values:
                await message.channel.send("## You can't remove a status you didn't add.")
                return

            if status_to_remove in user_status_values:
                remove_status(status_to_remove)
                await message.add_reaction("✅")
            else:
                message.add_reaction("❌")
                await message.channel.send("## I couldn't find that status among the ones you added.")

        if "ty chuju" in message.content.lower() and len(message.content) < 12 and message.author.id == self.target_user_id:
            await message.add_reaction("❤️")

        if message.content.startswith("!add_status "):
            # remove the "!add_status " prefix
            raw_args = message.content[len("!add_status "):].strip()

            # split by spaces
            parts = raw_args.split()

            print(parts)

            # minimum two elements required: [category] [content...]
            if len(parts) < 2:
                await message.channel.send(
                    "Usage: `!add_status [category] status content`\n"
                    "Example: `!add_status general Hello world!`"
                )
                return

            categories = get_all_categories()

            category = parts[0]

            if category not in [c['label'] for c in categories]:
                await message.add_reaction("❌")
                await message.channel.send(
                    f"Category '{category}' does not exist.\nAvailable categories:\n- "
                    + "\n- ".join(c['label'] for c in categories)
                )
                return

            new_status = " ".join(parts[1:]).strip()

            if not new_status:
                await message.channel.send("Provide the status text after the category 🤨")
                return


            if does_status_exist(new_status):
                await message.add_reaction("❌")
                await message.channel.send("That status already exists")
                return

            add_status_request(
                person_name=str(message.author),
                person_id=message.author.id,
                status=new_status,
                category=category
            )

            await message.add_reaction("✅")

        if message.content.startswith("!status_list "):
            category = message.content[len("!status_list "):].strip()
            statuses_in_category = get_statuses_by_category(category)

            if statuses_in_category:
                status_list = "\n".join(
                    f"- **{s['status']}** ({s['person_name']})"
                    for s in statuses_in_category
                )


                if len(status_list) > self.discord_message_length_limit:
                    await message.channel.send("There are too many statuses in this category to display.")
                else:
                    await message.channel.send(f"## Statuses in the '{category}' category:\n{status_list}")
            else:
                await message.channel.send(f"## No statuses in the '{category}' category.")

        if message.content == "!category_list":
            categories = get_all_categories()
            category_list = "\n- ".join(c['label'] for c in categories)
            category_list = "- " + category_list
            await message.channel.send(f"## Available status categories:\n{category_list}")

        if message.content.startswith("!add_category "):
            new_category = message.content[len("!add_category "):].strip()

            if " " in new_category:
                await message.channel.send("The category name cannot contain spaces.")
                return

            if new_category:
                add_category(
                    created_by_user_id=message.author.id,
                    label=new_category
                )
                await message.add_reaction("✅")
            else:
                await message.channel.send("You didn't provide a category name to add.")

        if message.content.startswith("!remove_category "):
            categories = get_all_categories()
            categories_labels = [c['label'] for c in categories]
            category_to_remove = message.content[len("!remove_category "):].strip()
            if category_to_remove:
                if category_to_remove in categories_labels:
                    created_by_user_id = next(c['created_by_user_id'] for c in categories if c['label'] == category_to_remove)
                    if created_by_user_id != message.author.id:
                        await message.channel.send(f"You can only delete categories that you added yourself.")
                        return
                    else:
                        remove_category(category_to_remove)
                        await message.add_reaction("✅")
                else:
                    await message.channel.send(f"Category not found: {category_to_remove}")
            else:
                await message.channel.send("You didn't provide a category name to remove.")

        if message.content == "!permissions_list":
            if message.author.id != self.user.id:
                return
            permissions = get_all_permissions()
            permission_list = "\n".join(
                f"- User ID: **{p['user_id']}**, Label: **{p['label']}**"
                for p in permissions
            )
            await message.channel.send(f"## List of users with permissions:\n{permission_list}")

        if message.content.startswith("!add_permission "):
            if message.author.id != self.user.id:
                return
            parts = message.content[len("!add_permission "):].strip().split()
            if len(parts) < 2:
                await message.channel.send("Usage: `!add_permission <user_id> <label>`")
                return

            try:
                user_id = int(parts[0])
            except ValueError:
                await message.channel.send("Invalid user_id. It must be a number.")
                return

            label = " ".join(parts[1:]).strip()
            add_permission(user_id, label)
            await message.add_reaction("✅")

        if message.content.startswith("!remove_permission "):
            if message.author.id != self.user.id:
                return
            parts = message.content[len("!remove_permission "):].strip().split()
            if len(parts) < 1:
                await message.channel.send("Usage: `!remove_permission <user_id>`")
                return

            try:
                user_id = int(parts[0])
            except ValueError:
                await message.channel.send("Invalid user_id. It must be a number.")
                return

            remove_permission(user_id)
            await message.add_reaction("✅")

        if message.content == "!rotate_status":
            if message.author.id != self.user.id:
                return
            self.rotate_status = not self.rotate_status
            status_text = "enabled" if self.rotate_status else "disabled"
            await message.channel.send(f"Automatic status rotation is now {status_text}.")

        if message.content == "!vedal_loop":
            if message.author.id != self.user.id:
                return
            self.vedal_loop = not self.vedal_loop
            status_text = "enabled" if self.vedal_loop else "disabled"
            await message.channel.send(f"Vedal watch loop is now {status_text}.")

        if message.content == "!help":
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
                "- **!add_status <status>**: Adds a new status to the suggestion pool\n"
                "- **!remove_status <id>**: Removes a status from the suggestion pool\n"

                "## Categories:\n"
                "- **!category_list**: Shows the list of available status categories\n"
                "- **!add_category <name>**: Adds a new status category\n"
                "- **!remove_category <name>**: Removes a status category (if you added it)\n"

                "## URL:\n"
                "- [github repo](https://github.com/Magiszonekk/discord_self_bot_magiszonek)"
            )
            await message.channel.send(help_text,suppress_embeds=True)

        if message.content == "!help 2":
            help_text = (
                "# Admin commands:\n"
                "## General:\n"
                "- **!rotate_status**: Enables/disables automatic status rotation\n"
                "- **!vedal_loop**: Enables/disables the loop that checks whether Vedal is online\n\n"

                "## Permissions:\n"
                "- **!permissions_list**: Shows the list of users with permissions\n"
                "- **!add_permission <user_id> <label>**: Adds a permission for a user\n"
                "- **!remove_permission <user_id>**: Removes a user's permission\n\n"

                "## URL:\n"
                "- [github repo](https://github.com/Magiszonekk/discord_self_bot_magiszonek)"
            )
            await message.channel.send(help_text,suppress_embeds=True)

    async def on_reaction_add(self, reaction, user):
        if user.id != self.user.id:
            return

        print(f"Reaction from {user}: {reaction.emoji} on message {reaction.message.id}")

        if str(reaction.emoji) == "👍":
            status_content = reaction.message.content
            if status_content.startswith("!add_status "):
                status_value = status_content[len("!add_status "):].strip()
                approve_status_by_value(status_value, user.id)
                await reaction.message.channel.send(f"Status '{status_value}' approved by {user}.")

    async def send_discord_message(self, message: str, user_id: int = None):
        if user_id is None:
            user_id = self.target_user_id

        user = self.get_user(user_id)
        if user is None:
            try:
                user = await self.fetch_user(user_id)
            except Exception as e:
                print("Cannot fetch user:", e)
                return

        try:
            await user.send(message)
            print("✅ Sent DM:", message)
        except Exception as e:
            print("❌ Failed to send DM:", e)
