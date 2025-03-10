# utils/logging.py

import datetime
import asyncio
from utils.config import LOG_CHANNEL_ID

INTERACTION_LOGS = []

async def log_interaction(user, command_name, details):
    """Log an interaction with a timestamp, the user, command name, and details."""
    timestamp = datetime.datetime.now().isoformat()
    log_entry = f"[{timestamp}] {user} used {command_name}: {details}"
    INTERACTION_LOGS.append(log_entry)

async def send_logs_periodically(bot, interval=5):
    """Periodically send accumulated logs to a designated channel."""
    await bot.wait_until_ready()
    if LOG_CHANNEL_ID is None:
        print("LOG_CHANNEL_ID not set; skipping periodic log posting.")
        return
    log_channel_id = int(LOG_CHANNEL_ID)
    while not bot.is_closed():
        if INTERACTION_LOGS:
            channel = bot.get_channel(log_channel_id)
            if channel is not None:
                log_message = "\n".join(INTERACTION_LOGS)
                try:
                    await channel.send(f"**Interaction Log:**\n{log_message}")
                except Exception as e:
                    print("Error sending log message:", e)
            INTERACTION_LOGS.clear()
        await asyncio.sleep(interval)
