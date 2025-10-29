import asyncio
from discord_module import MyClient
from is_vedal_online_module import vedal_watch_loop
from db_utils import init_db
from datetime import datetime
from cli import start_cli  
import time
from dotenv import load_dotenv
import os

load_dotenv()
DISCORD_TOKEN = os.getenv("TOKEN")

client = MyClient()

startup_time = datetime.now()

async def main():
    init_db()
    start_cli()  # uruchomienie interfejsu CLI
    async with client:
        asyncio.create_task(vedal_watch_loop(client, startup_time))
        await client.start(DISCORD_TOKEN)
        
asyncio.run(main())

# my id 670188112214753280