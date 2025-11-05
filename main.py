import asyncio
from discord_module import MyClient
from db_utils import init_db
from datetime import datetime
from cli import start_cli  
import time
from dotenv import load_dotenv
from db_utils import get_all_permissions, get_all_categories
import os

load_dotenv()
DISCORD_TOKEN = os.getenv("TOKEN")

client = MyClient()

startup_time = datetime.now()

async def main():
    init_db()
    start_cli()  # launch the CLI interface
    async with client:
        await client.start(DISCORD_TOKEN)
        
asyncio.run(main())
