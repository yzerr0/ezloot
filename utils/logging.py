# utils/logging.py
import datetime
import asyncio
import discord
from discord.ext import escape_markdown
from utils.config import LOG_CHANNEL_ID

INTERACTION_LOGS = []

def format_user(user: discord.User) -> str:
    """
    Return a formatted string with the user's base username (with markdown escaped)
    and their mention if available.
    """
    try:
        base_name = escape_markdown(user.name)
        mention = user.mention if hasattr(user, "mention") else user.name
        return f"**{base_name}** ({mention})"
    except Exception:
        return str(user)

async def log_interaction(user, command_name, details):
    """Log an interaction with a timestamp, the user, command name, and details."""
    formatted_user = format_user(user)
    timestamp = datetime.datetime.now().isoformat()
    log_entry = f"[{timestamp}] {formatted_user} used **{command_name}**: {details}"
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
