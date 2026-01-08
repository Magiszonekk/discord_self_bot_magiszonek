import os
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import List

LOG_DIR = Path(os.getenv("LOG_DIR", "logs"))
_LOG_LOCK = Lock()


def _get_log_file_for_date(date: datetime = None) -> Path:
    """Returns the log file path for a specific date."""
    if date is None:
        date = datetime.now()
    filename = f"bot_{date.strftime('%Y-%m-%d')}.log"
    return LOG_DIR / filename


def _get_current_log_file() -> Path:
    """Returns the log file path for today."""
    return _get_log_file_for_date(datetime.now())


def log(message: str, print_output: bool = False, level: str = "INFO") -> None:
    """
    Append a single log entry to today's log file.
    Each day gets a new log file: bot_YYYY-MM-DD.log
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"{timestamp} [{level.upper()}] {message}"

    if print_output:
        print(entry)

    log_file = _get_current_log_file()
    with _LOG_LOCK:
        with log_file.open("a", encoding="utf-8") as fp:
            fp.write(entry + "\n")


def get_log_files() -> List[Path]:
    """Returns a list of all log files, sorted by date (newest first)."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    files = list(LOG_DIR.glob("bot_*.log"))
    files.sort(reverse=True)
    return files


def get_latest_logs(lines: int = 20) -> List[str]:
    """
    Gets the latest log entries across all log files.
    Starts with today's log, then goes to previous days if needed.
    """
    result = []
    log_files = get_log_files()

    for log_file in log_files:
        if len(result) >= lines:
            break
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                file_lines = f.readlines()
                needed = lines - len(result)
                result = file_lines[-needed:] + result
        except Exception:
            continue

    return result[-lines:] if len(result) > lines else result


def get_logs_closest_to(target_dt: datetime, n: int = 10) -> str:
    """
    Finds log entries closest to the given datetime.
    Searches in the appropriate log file for that date.
    """
    log_file = _get_log_file_for_date(target_dt)

    if not log_file.exists():
        # Try to find the closest available log file
        available_files = get_log_files()
        if not available_files:
            return "No log files found."
        # Use the file closest to the target date
        log_file = available_files[0]  # Default to newest
        for f in available_files:
            try:
                # Extract date from filename
                date_str = f.stem.replace("bot_", "")
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                if file_date.date() <= target_dt.date():
                    log_file = f
                    break
            except ValueError:
                continue

    try:
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        return f"Error reading log file: {e}"

    if not lines:
        return "Log file is empty."

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

    return "".join(lines[closest_idx:closest_idx + n])


async def logs_message_handler(message, self):
    """Discord command handler for !logs - kept for backwards compatibility."""
    parts = message.content.strip().split()
    command_name = "!logs"

    # permissions
    if message.author.id != message.guild.me.id and message.author.id != message.client.user.id:
        self.log_command_usage(command_name, message.author, False, "Admin only")
        return

    # No arguments -> last 10 lines
    if len(parts) == 1:
        how_many = 10
        try:
            lines = get_latest_logs(how_many)
            out = "".join(lines)
            await message.channel.send(f"```{out}```")
            self.log_command_usage(command_name, message.author, True)
        except Exception as e:
            await message.channel.send(f"Failed to read log file: {e}")
            self.log_command_usage(command_name, message.author, False, str(e))
        return

    # Try to parse "how_many"
    idx = 1
    try:
        how_many = int(parts[idx])
        idx += 1
    except:
        how_many = 10

    # If only how_many provided
    if len(parts) == idx:
        try:
            lines = get_latest_logs(how_many)
            out = "".join(lines)
            await message.channel.send(f"```{out}```")
            self.log_command_usage(command_name, message.author, True)
        except Exception as e:
            await message.channel.send(f"Failed to read log file: {e}")
            self.log_command_usage(command_name, message.author, False, str(e))
        return

    # Date and time provided
    if len(parts) < idx + 2:
        await message.channel.send("Usage: `!logs <how_many> <day>-<month> <hour>:<minute>[:<second>]`")
        self.log_command_usage(command_name, message.author, False, "bad_args")
        return

    date_str = parts[idx]
    time_str = parts[idx + 1]

    try:
        d_str, m_str = date_str.split("-")
        day = int(d_str)
        month = int(m_str)
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

    try:
        out = get_logs_closest_to(target_dt, n=how_many)
        if len(out) > 1900:
            out = out[-1900:]
        await message.channel.send(f"```{out}```")
        self.log_command_usage(command_name, message.author, True)
    except Exception as e:
        await message.channel.send(f"Failed to read log file: {e}")
        self.log_command_usage(command_name, message.author, False, str(e))
