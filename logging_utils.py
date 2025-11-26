import os
from datetime import datetime
from pathlib import Path
from threading import Lock

LOG_DIR = Path(os.getenv("LOG_DIR", "logs"))
LOG_FILE = LOG_DIR / os.getenv("LOG_FILE_NAME", "bot.log")
_LOG_LOCK = Lock()


def log(message: str, print_output: bool = False, level: str = "INFO") -> None:
    """
    Append a single log entry to the log file and mirror it to stdout.
    """

    # if print_output:
    #     print(message)

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"{timestamp} [{level.upper()}] {message}"
    if print_output:
        print(entry)
    with _LOG_LOCK:
        with LOG_FILE.open("a", encoding="utf-8") as fp:
            fp.write(entry + "\n")

def get_logs_closest_to(filepath: str, target_dt: datetime, n: int = 10) -> str:
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    closest_idx = None
    closest_diff = None

    for i, line in enumerate(lines):
        if len(line) < 19:
            continue

        ts_str = line[:19]  # "YYYY-MM-DD HH:MM:SS"
        try:
            line_dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue

        diff = abs((line_dt - target_dt).total_seconds())
        if closest_diff is None or diff < closest_diff:
            closest_diff = diff
            closest_idx = i

    if closest_idx is None:
        return "No parsable timestamps found in log file."

    # 10 linii od najbliższej
    return "".join(lines[closest_idx:closest_idx + n])


async def logs_message_handler(message, self):
    parts = message.content.strip().split()
    command_name = "!logs"
    # permissions
    if message.author.id != message.guild.me.id and message.author.id != message.client.user.id:
        self.log_command_usage(command_name, message.author, False, "Admin only")
        return
    # brak argumentów -> ostatnie 10 linii
    if len(parts) == 1:
        how_many = 10
        try:
            with open("./logs/bot.log", "r", encoding="utf-8") as f:
                lines = f.readlines()
                out = "".join(lines[-how_many:])
            await message.channel.send(f"```{out}```")
            self.log_command_usage(command_name, message.author, True)
        except Exception as e:
            await message.channel.send(f"Failed to read log file: {e}")
            self.log_command_usage(command_name, message.author, False, str(e))
        return
    # Jeśli 2 element -> może to być ilość
    idx = 1
    # próbujemy sparsować "how_many"
    try:
        how_many = int(parts[idx])
        idx += 1
    except:
        how_many = 10  # defaul
    # jeśli po how_many nie ma daty → znaczy że użytkownik wpisał tylko "how_many"
    if len(parts) == idx:
        try:
            with open("./logs/bot.log", "r", encoding="utf-8") as f:
                lines = f.readlines()
                out = "".join(lines[-how_many:])
            await message.channel.send(f"```{out}```")
            self.log_command_usage(command_name, message.author, True)
        except Exception as e:
            await message.channel.send(f"Failed to read log file: {e}")
            self.log_command_usage(command_name, message.author, False, str(e))
        return
    # ---- Mamy datę i czas ---
    # parts[idx] = "26-11"
    # parts[idx+1] = "10:41[:07]
    if len(parts) < idx + 2:
        await message.channel.send("Usage: `!logs <how_many> <day>-<month> <hour>:<minute>[:<second>]`")
        self.log_command_usage(command_name, message.author, False, "bad_args")
        return
    date_str = parts[idx]
    time_str = parts[idx + 1]
    try:
        # parsowanie daty
        d_str, m_str = date_str.split("-")
        day = int(d_str)
        month = int(m_str)
        # parsowanie czasu
        t = time_str.split(":")
        hour = int(t[0])
        minute = int(t[1])
        second = int(t[2]) if len(t) > 2 else 0
        year = datetime.now().year
        target_dt = datetime(year, month, day, hour, minute, second)
    except Exception as e:
        await message.channel.send("Usage: `!logs <how_many> <day>-<month> <hour>:<minute>[:<second>]`")
        self.log_command_usage(command_name, message.author, False, f"bad_args {e}")
        return
    # pobieranie logów najbliższych dacie
    try:
        out = get_logs_closest_to("./logs/bot.log", target_dt, n=how_many)
        if len(out) > 1900:
            out = out[-1900:]
        await message.channel.send(f"```{out}```")
        self.log_command_usage(command_name, message.author, True)
    except Exception as e:
        await message.channel.send(f"Failed to read log file: {e}")                                 
        self.log_command_usage(command_name, message.author, False, str(e))