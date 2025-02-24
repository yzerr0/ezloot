import os
import json
import discord
from discord.ext import commands
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore
import asyncio

# load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN is None:
    raise ValueError("Missing discord token.")

# minified json string
FIREBASE_CERTIFICATE = os.getenv("FIREBASE_CERTIFICATE")
if FIREBASE_CERTIFICATE is None:
    raise ValueError("Missing FIREBASE_CERTIFICATE config.")

# initialize firebase admin
firebase_config = json.loads(FIREBASE_CERTIFICATE)
cred = credentials.Certificate(firebase_config)
firebase_admin.initialize_app(cred)
db = firestore.client()

# bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!ezloot ', intents=intents)

# list of valid gear slots
GEAR_SLOTS = ["Head", "Cloak", "Chest", "Gloves", "Legs", "Boots", "Necklace", "Belt", "Ring 1", "Ring 2"]

# admin id (replace with actual discord ids)
ADMIN_IDS = {123456789012345678}  # example admin id

def is_admin(ctx):
    """Check if the invoking user is an admin by ID or has administrator permissions."""
    return ctx.author.id in ADMIN_IDS or (ctx.guild is not None and ctx.author.guild_permissions.administrator)

# firestore helper functions
async def get_user(user_id: str):
    """Retrieve the user document from Firestore."""
    doc_ref = db.collection("users").document(user_id)
    doc = await asyncio.to_thread(doc_ref.get)
    if doc.exists:
        return doc.to_dict()
    return None

async def register_user(user_id: str, username: str):
    """Register a new user with default gear and empty loot."""
    doc_ref = db.collection("users").document(user_id)
    doc = await asyncio.to_thread(doc_ref.get)
    if doc.exists:
        return False
    data = {
        "username": username,
        "gear": {slot: {"item": None, "looted": False} for slot in GEAR_SLOTS},
        "loot": []
    }
    await asyncio.to_thread(doc_ref.set, data)
    return True

async def update_gear_item(user_id: str, slot: str, item: str):
    """Update the gear item for a given slot."""
    doc_ref = db.collection("users").document(user_id)
    await asyncio.to_thread(doc_ref.update, {f"gear.{slot}.item": item})

async def lock_gear_slot(user_id: str, slot: str):
    """Mark a gear slot as locked (loot assigned)."""
    doc_ref = db.collection("users").document(user_id)
    await asyncio.to_thread(doc_ref.update, {f"gear.{slot}.looted": True})

async def add_loot(user_id: str, loot_entry: str):
    """Add a loot entry to the user's record using Firestore's ArrayUnion."""
    doc_ref = db.collection("users").document(user_id)
    await asyncio.to_thread(doc_ref.update, {"loot": firestore.ArrayUnion([loot_entry])})

# bot events
@bot.event
async def on_ready():
    print(f"EZLoot bot is online as {bot.user}.")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send(f"{ctx.author.mention} That command does not exist. Please check your command and try again.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"{ctx.author.mention} Missing required argument. Please check your command and try again.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"{ctx.author.mention} One or more arguments are invalid. Please check your command and try again.")
    else:
        print(f"Unhandled error: {error}")
        await ctx.send(f"{ctx.author.mention} An error occurred while processing your command.")

# user commands

@bot.command(name="register")
async def register(ctx):
    """Register a user by initializing their gear slots in Firestore."""
    user_id = str(ctx.author.id)
    user_data = await get_user(user_id)
    if user_data:
        await ctx.send(f"{ctx.author.mention}, you are already registered.")
        return
    success = await register_user(user_id, ctx.author.name)
    if success:
        await ctx.send(
            f"{ctx.author.mention}, you have been registered!\n"
            "Use `!ezloot set <slot> <item>` to record your gear for each slot."
        )
    else:
        await ctx.send(f"{ctx.author.mention}, registration failed. Please try again.")

@bot.command(name="set")
async def set_item(ctx, slot: str, *, item: str):
    """Set an item for a given gear slot."""
    user_id = str(ctx.author.id)
    user_data = await get_user(user_id)
    if not user_data:
        await ctx.send(f"{ctx.author.mention}, please register first using `!ezloot register`.")
        return
    slot = slot.capitalize()
    if slot not in GEAR_SLOTS:
        await ctx.send(f"{ctx.author.mention}, `{slot}` is not a valid gear slot. Valid slots: {', '.join(GEAR_SLOTS)}")
        return
    gear = user_data.get("gear", {})
    slot_data = gear.get(slot, {})
    if slot_data.get("looted"):
        await ctx.send(f"{ctx.author.mention}, your **{slot}** slot is locked as loot has already been assigned.")
        return
    if slot_data.get("item") is not None:
        await ctx.send(
            f"{ctx.author.mention}, you already have an item recorded for **{slot}**. "
            f"Use `!ezloot edit {slot} <new_item>` to change it."
        )
        return
    await update_gear_item(user_id, slot, item)
    await ctx.send(f"{ctx.author.mention}, your **{slot}** has been set to **{item}**.")

@bot.command(name="edit")
async def edit_item(ctx, slot: str, *, new_item: str):
    """Edit the recorded item for a given gear slot."""
    user_id = str(ctx.author.id)
    user_data = await get_user(user_id)
    if not user_data:
        await ctx.send(f"{ctx.author.mention}, please register first using `!ezloot register`.")
        return
    slot = slot.capitalize()
    if slot not in GEAR_SLOTS:
        await ctx.send(f"{ctx.author.mention}, `{slot}` is not a valid gear slot.")
        return
    gear = user_data.get("gear", {})
    slot_data = gear.get(slot, {})
    if slot_data.get("looted"):
        await ctx.send(f"{ctx.author.mention}, you cannot change **{slot}** because loot has been assigned.")
        return
    if slot_data.get("item") is None:
        await ctx.send(
            f"{ctx.author.mention}, you do not have an item set for **{slot}** yet. "
            f"Use `!ezloot set {slot} <item>` to set it first."
        )
        return
    await update_gear_item(user_id, slot, new_item)
    await ctx.send(f"{ctx.author.mention}, your **{slot}** has been updated to **{new_item}**.")

@bot.command(name="showgear")
async def show_gear(ctx):
    """Display the user's currently recorded gear along with lock status."""
    user_id = str(ctx.author.id)
    user_data = await get_user(user_id)
    if not user_data:
        await ctx.send(f"{ctx.author.mention}, you are not registered yet. Use `!ezloot register` first.")
        return
    gear = user_data.get("gear", {})
    message = f"{ctx.author.mention}'s gear:\n"
    for slot, data in gear.items():
        status = "Locked" if data.get("looted") else "Editable"
        item = data.get("item") if data.get("item") is not None else "Not set"
        message += f"**{slot}**: {item} ({status})\n"
    await ctx.send(message)

@bot.command(name="showloot")
async def show_loot(ctx, user: discord.Member = None):
    """
    Show receievd loot for a specific user.
    If no user is provided, show loot for the author.
    """
    target = user if user else ctx.author
    user_id = str(target.id)
    user_data = await get_user(user_id)
    if not user_data or not user_data.get("loot"):
        await ctx.send(f"{target.mention} has not received any loot.")
        return
    loot_list = user_data.get("loot")
    await ctx.send(f"{target.mention} has received:\n" + "\n".join(loot_list))

# admin commands

@bot.command(name="listusers")
@commands.check(is_admin)
async def list_users(ctx):
    """Admin: List all registered users."""
    def fetch_users():
        return list(db.collection("users").stream())
    docs = await asyncio.to_thread(fetch_users)
    if not docs:
        await ctx.send("No users registered yet.")
        return
    message = "Registered Users:\n"
    for doc in docs:
        data = doc.to_dict()
        user_id = doc.id
        try:
            user = await bot.fetch_user(int(user_id))
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
    def fetch_users():
        return list(db.collection("users").stream())
    docs = await asyncio.to_thread(fetch_users)
    found_users = []
    for doc in docs:
        data = doc.to_dict()
        gear = data.get("gear", {})
        for slot_data in gear.values():
            if slot_data.get("item") and slot_data.get("item").lower() == item.lower():
                try:
                    user = await bot.fetch_user(int(doc.id))
                    found_users.append(user.name)
                except Exception:
                    found_users.append(f"UserID {doc.id}")
                break
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
    user_id = str(user.id)
    user_data = await get_user(user_id)
    if not user_data:
        await ctx.send(f"{user.mention} is not registered.")
        return
    slot = slot.capitalize()
    if slot not in GEAR_SLOTS:
        await ctx.send(f"{ctx.author.mention}, `{slot}` is not a valid gear slot. Valid slots: {', '.join(GEAR_SLOTS)}")
        return
    gear = user_data.get("gear", {})
    slot_data = gear.get(slot, {})
    if slot_data.get("item") is None:
        await ctx.send(f"{user.mention} does not have an item set for **{slot}**.")
        return
    if slot_data.get("looted"):
        await ctx.send(f"{user.mention}'s **{slot}** item has already been awarded.")
        return
    await lock_gear_slot(user_id, slot)
    loot_entry = f"{slot}: {slot_data['item']}"
    await add_loot(user_id, loot_entry)
    await ctx.send(f"Loot assigned to {user.mention} for **{slot}**: **{slot_data['item']}**.")

@bot.command(name="guildtotal")
@commands.check(is_admin)
async def guild_total(ctx):
    """Admin: Show the total count of loot pieces awarded across all users."""
    def fetch_users():
        return list(db.collection("users").stream())
    docs = await asyncio.to_thread(fetch_users)
    total_loot = 0
    for doc in docs:
        data = doc.to_dict()
        loot = data.get("loot", [])
        total_loot += len(loot)
    await ctx.send(f"The guild has received a total of **{total_loot}** loot pieces.")

# run the bot
bot.run(TOKEN)
