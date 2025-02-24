import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN is None:
    raise ValueError("Missing discord token.")

# bot setup
intents = discord.Intents.default()
intents.message_content = True  # Needed for message content access
bot = commands.Bot(command_prefix='!ezloot ', intents=intents)

# user_gear maps user_id to a dict of gear slots.
# each slot is a dict with keys:
#    "item": the recorded item (string)
#    "looted": boolean flag to indicate if loot for that slot has been awarded.
user_gear = {}

# user_loot maps user_id to a list of loot awards.
# each entry is a string like "Head: Winwood" (slot: recorded item).
user_loot = {}

# list of valid gear slots
GEAR_SLOTS = ["Head", "Cloak", "Chest", "Gloves", "Legs", "Boots", "Necklace", "Belt", "Ring 1", "Ring 2"]

# admin ids (replace with actual discord ids)
ADMIN_IDS = {123456789012345678}  # example admin id

def is_admin(ctx):
    """Check if the invoking user is an admin by ID or has administrator permissions."""
    return ctx.author.id in ADMIN_IDS or (ctx.guild is not None and ctx.author.guild_permissions.administrator)

# bot events
@bot.event
async def on_ready():
    print(f"EZLoot bot is online as {bot.user}.")

# Global error handler to catch unknown commands and missing parameters
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send(f"{ctx.author.mention} That command does not exist. Please check your command and try again.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"{ctx.author.mention} Missing required argument. Please check your command and try again.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"{ctx.author.mention} One or more arguments are invalid. Please check your command and try again.")
    else:
        # Log the error in the console and send a generic error message to the user.
        print(f"Unhandled error: {error}")
        await ctx.send(f"{ctx.author.mention} An error occurred while processing your command.")

# user commands

@bot.command(name="register")
async def register(ctx):
    """Register a user by initializing their gear slots."""
    if ctx.author.id in user_gear:
        await ctx.send(f"{ctx.author.mention}, you are already registered.")
        return

    # initialize each gear slot with no item and unlocked status
    user_gear[ctx.author.id] = {slot: {"item": None, "looted": False} for slot in GEAR_SLOTS}
    await ctx.send(
        f"{ctx.author.mention}, you have been registered!\n"
        f"Use `!ezloot set <slot> <item>` to record your gear for each slot."
    )

@bot.command(name="set")
async def set_item(ctx, slot: str, *, item: str):
    """Set an item for a given gear slot."""
    # check registration
    if ctx.author.id not in user_gear:
        await ctx.send(f"{ctx.author.mention}, please register first using `!ezloot register`.")
        return

    # normalize slot name
    slot = slot.capitalize()
    if slot not in GEAR_SLOTS:
        await ctx.send(f"{ctx.author.mention}, `{slot}` is not a valid gear slot. Valid slots: {', '.join(GEAR_SLOTS)}")
        return

    user_slot = user_gear[ctx.author.id][slot]
    if user_slot["looted"]:
        await ctx.send(f"{ctx.author.mention}, your **{slot}** slot is locked as loot has already been assigned.")
        return

    if user_slot["item"] is not None:
        await ctx.send(
            f"{ctx.author.mention}, you already have an item recorded for **{slot}**. "
            f"Use `!ezloot edit {slot} <new_item>` to change it."
        )
        return

    user_gear[ctx.author.id][slot]["item"] = item
    await ctx.send(f"{ctx.author.mention}, your **{slot}** has been set to **{item}**.")

@bot.command(name="edit")
async def edit_item(ctx, slot: str, *, new_item: str):
    """Edit the recorded item for a given gear slot."""
    # check registration
    if ctx.author.id not in user_gear:
        await ctx.send(f"{ctx.author.mention}, please register first using `!ezloot register`.")
        return

    slot = slot.capitalize()
    if slot not in GEAR_SLOTS:
        await ctx.send(f"{ctx.author.mention}, `{slot}` is not a valid gear slot.")
        return

    user_slot = user_gear[ctx.author.id][slot]
    if user_slot["looted"]:
        await ctx.send(f"{ctx.author.mention}, you cannot change **{slot}** because loot has been assigned.")
        return

    if user_slot["item"] is None:
        await ctx.send(
            f"{ctx.author.mention}, you do not have an item set for **{slot}** yet. "
            f"Use `!ezloot set {slot} <item>` to set it first."
        )
        return

    user_gear[ctx.author.id][slot]["item"] = new_item
    await ctx.send(f"{ctx.author.mention}, your **{slot}** has been updated to **{new_item}**.")

@bot.command(name="showgear")
async def show_gear(ctx):
    """Display the user's currently recorded gear along with lock status."""
    if ctx.author.id not in user_gear:
        await ctx.send(f"{ctx.author.mention}, you are not registered yet. Use `!ezloot register` first.")
        return

    message = f"{ctx.author.mention}'s gear:\n"
    for slot, data in user_gear[ctx.author.id].items():
        status = "Locked" if data["looted"] else "Editable"
        item = data["item"] if data["item"] is not None else "Not set"
        message += f"**{slot}**: {item} ({status})\n"
    await ctx.send(message)

# admin commands

@bot.command(name="listusers")
@commands.check(is_admin)
async def list_users(ctx):
    """Admin: List all registered users."""
    if not user_gear:
        await ctx.send("No users registered yet.")
        return

    message = "Registered Users:\n"
    for user_id in user_gear:
        try:
            user = await bot.fetch_user(user_id)
            message += f"- {user.name} ({user_id})\n"
        except Exception:
            message += f"- Unknown User ({user_id})\n"
    await ctx.send(message)

@bot.command(name="finditem")
@commands.check(is_admin)
async def find_item(ctx, *, item: str):
    """
    Admin: Find users who have recorded a specific item in any gear slot.
    The check is case-insensitive.
    """
    found_users = []
    for user_id, gear in user_gear.items():
        if any(data["item"] and data["item"].lower() == item.lower() for data in gear.values()):
            try:
                user = await bot.fetch_user(user_id)
                found_users.append(user.name)
            except Exception:
                found_users.append(f"UserID {user_id}")
    if not found_users:
        await ctx.send(f"No users found with item **{item}**.")
    else:
        await ctx.send(f"Users with item **{item}**: {', '.join(found_users)}")

@bot.command(name="assignloot")
@commands.check(is_admin)
async def assign_loot(ctx, user: discord.Member, slot: str):
    """
    Admin: Assign loot to a user based on one of their recorded gear items.
    Once assigned, that gear slot becomes locked (cannot be updated).
    Usage: !ezloot assignloot @User <slot>
    """
    if user.id not in user_gear:
        await ctx.send(f"{user.mention} is not registered.")
        return

    slot = slot.capitalize()
    if slot not in GEAR_SLOTS:
        await ctx.send(f"{ctx.author.mention}, `{slot}` is not a valid gear slot. Valid slots: {', '.join(GEAR_SLOTS)}")
        return

    user_slot = user_gear[user.id][slot]
    if user_slot["item"] is None:
        await ctx.send(f"{user.mention} does not have an item set for **{slot}**.")
        return

    if user_slot["looted"]:
        await ctx.send(f"{user.mention}'s **{slot}** item has already been awarded.")
        return

    # lock the gear slot and record the loot award
    user_gear[user.id][slot]["looted"] = True
    loot_entry = f"{slot}: {user_slot['item']}"
    user_loot.setdefault(user.id, []).append(loot_entry)
    await ctx.send(f"Loot assigned to {user.mention} for **{slot}**: **{user_slot['item']}**.")

@bot.command(name="guildtotal")
@commands.check(is_admin)
async def guild_total(ctx):
    """Admin: Show the total count of loot pieces awarded across all users."""
    total_loot = sum(len(loots) for loots in user_loot.values())
    await ctx.send(f"The guild has received a total of **{total_loot}** loot pieces.")

@bot.command(name="showloot")
async def show_loot_self(ctx, user: discord.Member = None):
    """
    Show loot for a specific user.
    If no user is provided, show loot for the author.
    Both admins and regular users can use this.
    """
    target = user if user else ctx.author
    loot_list = user_loot.get(target.id, [])
    if not loot_list:
        await ctx.send(f"{target.mention} has not received any loot.")
    else:
        await ctx.send(f"{target.mention} has received:\n" + "\n".join(loot_list))

# run the bot
bot.run(TOKEN)
