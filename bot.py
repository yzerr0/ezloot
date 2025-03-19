# bot.py
import discord
import json
from discord.ext import commands
import firebase_admin
from firebase_admin import credentials
import asyncio
from utils.config import TOKEN, FIREBASE_CERTIFICATE

# load env & firebase credentials
if not firebase_admin._apps:
    firebase_config_str = FIREBASE_CERTIFICATE.strip().replace("\n", "")
    firebase_config = json.loads(firebase_config_str)
    cred = credentials.Certificate(firebase_config)
    firebase_admin.initialize_app(cred)

# bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!ezdev ", intents=intents)
bot.remove_command("help")

# load extensions
async def load_extensions():
    await bot.load_extension("cogs.user_commands")
    await bot.load_extension("cogs.admin_commands")

@bot.event
async def setup_hook():
    from utils.db import load_admin_ids
    await load_admin_ids()
    await load_extensions()
    from utils.logging import send_logs_periodically
    asyncio.create_task(send_logs_periodically(bot))

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send(f"{ctx.author.mention} That command does not exist. Please check your command and try again.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"{ctx.author.mention} Missing required argument. Please check your command and try again.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"{ctx.author.mention} One or more arguments are invalid. Please check your command and try again.")
    elif isinstance(error, commands.CheckFailure):
        await ctx.send(f"{ctx.author.mention} You do not have permission to use that command, or it cannot be used here.")
    else:
        print(f"Unhandled error: {error}")
        await ctx.send(f"{ctx.author.mention} An error occurred while processing your command.")

bot.run(TOKEN)
