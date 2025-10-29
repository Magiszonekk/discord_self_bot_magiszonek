import discord
import asyncio
import random
from datetime import datetime, timedelta
from db_utils import get_all_statuses
from db_utils import add_status_request
from db_utils import get_added_statuses_from_user
from db_utils import get_all_permissions
from db_utils import approve_status_by_value
import os

class MyClient(discord.Client):
    def __init__(self):
        # self_bot=True jest wymagane dla discord.py-self
        super().__init__(self_bot=True)

        self.target_user_id = 532637329211392002  # <- twój ID lub ID do powiadomień
        self.already_notified_today = False
        self.bg_tasks_started = False
        # self.status_rotation_interval = 15 * 60  # co ile sekund zmieniać status
        self.status_rotation_interval = {"min": 25, "max": 45}  # losowo co ile minut zmieniać status
        self.users_with_permissions = [
            299406453142323205,
            532637329211392002,
            427698599179059202,
            214754053534515201,
            725798401895038996
        ]
        # self.users_with_permissions = get_all_permissions()

        self.statuses = [
            "jedziesz łowić ryby - staw kolanowy",
            "twój stary gryzie ludzi - pseudonim sekator",
            "twój stary ma jedynki jak drzwi w salonie",
            "twój stary CPN zajebał paliwa galon",
            "nie bębę dłużej się żalić, ide wszystkich żydów spalić",
            "stary się nie rusza #nieruchomość",
            "twoja matka jest łysa - pseudonim kolano",
            "twoja matka siny łeb - pseudonim avatar",
            "twój stary struga cie w rowa - pseudonim dżepetto",
            "twój stary widzi ciebie matke - dwa worki treningowe",
            "pewien malarz to miał racje, popieram eksterminacje",
            "twoja stara na drugie - sławek w dowodzie",
            "matka drze morde, stary wali jej z karata",
            "jesteś wrogiem izraela, więc mam w tobie przyjaciela",
            "krzyczę głośno jebac żydów, mówię to wszystkim bez wstydu",
            "czas wyplenić to dziadostwo - niech już skończy się żydostwo",
            "w móglach ludziom kręcą korbą, więc na ryj dostaną kolbą",
            "7,2% to jest proste - kuflowe mocne",
            "do zobaczenia pod mostem - kuflowe mocne",
            "na mnie leci tylko deszcz",
            "szczęśliwy czasu nie liczy tak mawia się od wieków - wstaje 04:12 i 12 milisekund",
            "sutener żuli - chodzę w hawajskiej koszuki",
            "jestem sutenerem żuli - amputuje zulom huje - dorabiając cyce licze że nikt sie nie zorientuje",
            "buszuje po melinach, oferuje tanie wina, a gdy koleś się nie zgadza - uprowadzam skurwysyna",
            "ty pierdolony menelu niezła z ciebie maniura",
            "Mów do bogdana Roksana, Jan to zboczona Iwona",
            "Nie dowiary, nawet jest twój stary, dał Zbyszkowi kwiaty podpisane dla Tamary",
        ]

    async def on_ready(self):
        print("Logged on as", self.user)

        if not self.bg_tasks_started:
            self.bg_tasks_started = True
            asyncio.create_task(self.rotate_status_task())
            # asyncio.create_task(self.daily_status_task())
            # vedal_watch_loop puszczamy z main.py

    async def daily_status_task(self):
        while True:
            now = datetime.now()
            target = now.replace(hour=8, minute=0, second=0, microsecond=0)

            if now >= target:
                target += timedelta(days=1)

            wait_seconds = (target - now).total_seconds()
            print(f"Czekam {wait_seconds/3600:.2f}h do 8:00...")

            await asyncio.sleep(wait_seconds)

            new_status = random.choice(self.statuses)
            print(f"[{datetime.now():%H:%M}] Zmieniam status na: {new_status}")

            try:
                await self.change_presence(
                    activity=discord.CustomActivity(new_status),
                    status=discord.Status.online,
                    edit_settings=True
                )
            except Exception as e:
                print("change_presence error (daily):", e)

    async def rotate_status_task(self):
        while True:
            try:
                activity = discord.CustomActivity(random.choice(self.statuses))
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
        # ignoruj własne wiadomości
        if message.author.id not in [self.user.id, *self.users_with_permissions]:
        # if message.author.id not in [self.user.id, *[u["user_id"] for u in self.users_with_permissions]]:
            return
            
        print(f"Message from {message.author}: {message.content}")

        if message.content == "!ping":
            await message.channel.send("pong")

        if message.content == "!my_statuses":
            user_statuses = get_added_statuses_from_user(message.author.id)
            if user_statuses:
                status_list = "\n".join(f"- {s[3]} (dodano: {s[4]})" for s in user_statuses)
                await message.channel.send(f"Twoje dodane statusy:\n{status_list}")
            else:
                await message.channel.send("Nie dodałeś jeszcze żadnych statusów.")

        if "ty chuju" in message.content.lower() and len(message.content) < 12 and message.author.id == self.target_user_id:
            await message.add_reaction("❤️")

        if message.content.startswith("!add_status "):
            new_status = message.content[len("!add_status "):].strip()
            if new_status:
                add_status_request(
                    person_name=str(message.author),
                    person_id=message.author.id,
                    status=new_status
                )
                # await message.channel.send(f"Dodano nowy status: {new_status}")
                await message.add_reaction("✅")
            else:
                await message.channel.send("Nie podałeś statusu do dodania.")

        if message.content == "!status_list":
            # status_list = "\n".join(f"- {s[1]} (ID: {s[0]})" for s in get_all_statuses())
            #status list from self.statuses
            status_list = "\n".join(f"- {s}" for s in self.statuses )
            await message.channel.send(f"Dostępne statusy:\n{status_list}")

        if message.content == "!cls" and message.author.id == self.user.id:
            os.system('cls' if os.name == 'nt' else 'clear')

        if message.content == "!help":
            help_text = (
                "Dostępne komendy:\n"
                "- !ping: Odpowiada 'pong'\n"
                "- !my_statuses: Pokazuje twoje dodane propozycje statusów\n"
                "- !add_status <status>: Dodaje nowy status do bazy propozycji\n"
                "- !status_list: Pokazuje listę dostępnych statusów\n"
                "- !cls: Czyści konsolę (tylko dla właściciela bota)\n"
                "- !help: Pokazuje tę wiadomość pomocy"
            )
            await message.channel.send(help_text)
                
    async def on_reaction_add(self, reaction, user):
        # if user.id not in [self.user.id, *self.users_with_permissions]:
        if user.id != self.user.id:
            return

        print(f"Reaction from {user}: {reaction.emoji} on message {reaction.message.id}")

        if str(reaction.emoji) == "👍":
            status_content = reaction.message.content
            if status_content.startswith("!add_status "):
                status_value = status_content[len("!add_status "):].strip()
                approve_status_by_value(status_value, user.id)
                await reaction.message.channel.send(f"Status '{status_value}' zatwierdzony przez {user}.")

    async def send_discord_message(self, message: str, user_id: int = None):
        if user_id is None:
            user_id = self.target_user_id

        user = self.get_user(user_id)
        if user is None:
            try:
                user = await self.fetch_user(user_id)
            except Exception as e:
                print("Nie mogę pobrać usera:", e)
                return

        try:
            await user.send(message)
            print("✅ Wysłałem DM:", message)
        except Exception as e:
            print("❌ Nie udało się wysłać DM:", e)
