import threading
import os

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

def cli_loop():
    """Prosty CLI loop działający w osobnym wątku."""
    print("CLI ready 😎 (komenda: cls)")
    while True:
        try:
            raw = input("> ").strip().lower()
        except EOFError:
            break  # np. terminal zamknięty

        if not raw:
            continue

        if raw == "cls":
            clear_screen()
        else:
            print(f"nieznana komenda: {raw}")

def start_cli():
    """Uruchamia CLI w tle (nie blokuje asyncio)."""
    thread = threading.Thread(target=cli_loop, daemon=True)
    thread.start()
