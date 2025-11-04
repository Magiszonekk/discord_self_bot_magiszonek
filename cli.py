import threading
import os

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

def cli_loop():
    """Simple CLI loop running in a separate thread."""
    print("CLI ready 😎 (command: cls)")
    while True:
        try:
            raw = input("> ").strip().lower()
        except EOFError:
            break  # e.g. terminal closed

        if not raw:
            continue

        if raw == "cls" or raw == "csl":
            # csl because common typo
            clear_screen()
        else:
            print(f"unknown command: {raw}")

def start_cli():
    """Starts the CLI in the background (does not block asyncio)."""
    thread = threading.Thread(target=cli_loop, daemon=True)
    thread.start()
