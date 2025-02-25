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

FIREBASE_CERTIFICATE = os.getenv("FIREBASE_CERTIFICATE")
if FIREBASE_CERTIFICATE is None:
    raise ValueError("Missing FIREBASE_CERTIFICATE config.")

# sanitize and parse the firebase certificate
firebase_config_str = FIREBASE_CERTIFICATE.strip().replace("\n", "")
firebase_config = json.loads(firebase_config_str)

# initialize firebase admin
cred = credentials.Certificate(firebase_config)
firebase_admin.initialize_app(cred)
db = firestore.client()

# bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!ezloot ', intents=intents)

# list of valid gear slots
GEAR_SLOTS = ["Head", "Cloak", "Chest", "Gloves", "Legs", "Boots", "Necklace", "Belt", "Ring 1", "Ring 2"]

# admin ids
ADMIN_IDS = set()

async def load_admin_ids():
    """
    Load admin IDs from Firestore.
    Assumes a document at config/admins with a field "ids" containing an array of IDs.
    """
    global ADMIN_IDS
    doc_ref = db.collection("config").document("admins")
    doc = await asyncio.to_thread(doc_ref.get)
    if doc.exists:
        data = doc.to_dict()
        ids = data.get("ids", [])
        ADMIN_IDS = set(int(i) for i in ids)
    else:
        ADMIN_IDS = set()

def is_admin(ctx):
    """Check if the invoking user is an admin by ID or has administrator permissions."""
    return ctx.author.id in ADMIN_IDS or (ctx.guild is not None and ctx.author.guild_permissions.administrator)

# helper function to generate a canonical loot entry (for both regular and bonus loot)
def canonical_loot_entry(slot: str, item: str) -> str:
    """
    Generate a canonical loot entry.
    Ensures the slot is capitalized and the item is lowercased and stripped of extra spaces.
    Format: "Slot: item"
    """
    return f"{slot.strip().capitalize()}: {item.strip().lower()}"

# optional helper to normalize an item string for searching
def normalize_item(item: str) -> str:
    return item.strip().lower()

# firestore helper functions
async def get_user(user_id: str):
    """Retrieve the user document from Firestore."""
    doc_ref = db.collection("users").document(user_id)
    doc = await asyncio.to_thread(doc_ref.get)
    if doc.exists:
        return doc.to_dict()
    return None

async def register_user(user_id: str, username: str):
    """Register a new user with default gear, empty loot, and empty bonus loot."""
    doc_ref = db.collection("users").document(user_id)
    doc = await asyncio.to_thread(doc_ref.get)
    if doc.exists:
        return False
    data = {
        "username": username,
        "gear": {slot: {"item": None, "looted": False} for slot in GEAR_SLOTS},
        "loot": [],
        "bonusloot": [] 
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

async def unlock_gear_slot(user_id: str, slot: str):
    """Unlock a gear slot (mark loot as not assigned)."""
    doc_ref = db.collection("users").document(user_id)
    await asyncio.to_thread(doc_ref.update, {f"gear.{slot}.looted": False})

async def add_loot(user_id: str, loot_entry: str):
    """Add a loot entry to the user's record using Firestore's ArrayUnion."""
    doc_ref = db.collection("users").document(user_id)
    await asyncio.to_thread(doc_ref.update, {"loot": firestore.ArrayUnion([loot_entry])})

async def add_bonusloot(user_id: str, bonusloot_entry: str):
    """Add a bonus loot entry to the user's record using Firestore's ArrayUnion."""
    doc_ref = db.collection("users").document(user_id)
    await asyncio.to_thread(doc_ref.update, {"bonusloot": firestore.ArrayUnion([bonusloot_entry])})

async def remove_gear_item(user_id: str, slot: str):
    """Remove the gear item for a given slot (reset it to None and unlock it)."""
    doc_ref = db.collection("users").document(user_id)
    await asyncio.to_thread(doc_ref.update, {f"gear.{slot}.item": None, f"gear.{slot}.looted": False})

async def remove_loot(user_id: str, loot_entry: str):
    """Remove a loot entry from the user's record using Firestore's ArrayRemove."""
    doc_ref = db.collection("users").document(user_id)
    await asyncio.to_thread(doc_ref.update, {"loot": firestore.ArrayRemove([loot_entry])})

async def remove_bonusloot(user_id: str, bonusloot_entry: str):
    """Remove a bonus loot entry from the user's record using Firestore's ArrayRemove."""
    doc_ref = db.collection("users").document(user_id)
    await asyncio.to_thread(doc_ref.update, {"bonusloot": firestore.ArrayRemove([bonusloot_entry])})

# bot events
@bot.event
async def on_ready():
    await load_admin_ids()
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
    # formatted output for gear
    lines = [f"**{slot}**: {data.get('item', 'Not set')} — {'Locked' if data.get('looted') else 'Editable'}" for slot, data in gear.items()]
    message = f"**{ctx.author.name}'s Gear:**\n" + "\n".join(lines)
    await ctx.send(message)

@bot.command(name="showloot")
async def show_loot(ctx, user: discord.Member = None):
    """
    Show received loot for a specific user.
    If no user is provided, show loot for the author.
    """
    target = user if user else ctx.author
    user_id = str(target.id)
    user_data = await get_user(user_id)
    if not user_data:
        await ctx.send(f"{target.mention} is not registered.")
        return
    normal_loot = user_data.get("loot", [])
    bonus_loot = user_data.get("bonusloot", [])
    
    response_lines = [f"**{target.name}'s Loot:**"]
    if normal_loot:
        response_lines.append("**Regular Loot:**")
        response_lines.extend(f"- {entry}" for entry in normal_loot)
    else:
        response_lines.append("No regular loot assigned.")
    
    response_lines.append("")  # blank line separator
    if bonus_loot:
        response_lines.append("**Bonus Loot:**")
        response_lines.extend(f"- {entry}" for entry in bonus_loot)
    else:
        response_lines.append("No bonus loot assigned.")
    
    await ctx.send("\n".join(response_lines))
    
@bot.command(name="commands")
async def help_command(ctx):
    """Display a list of all user and admin commands."""
    help_text = (
        "**User Commands:**\n"
        "`!ezloot register` - Register yourself and initialize your gear.\n"
        "`!ezloot set <slot> <item>` - Record an item for a specific gear slot.\n"
        "`!ezloot edit <slot> <new_item>` - Edit the recorded item for a specific gear slot.\n"
        "`!ezloot showgear` - Display your currently recorded gear.\n"
        "`!ezloot showloot [@User]` - Show loot for yourself or a specified user.\n"
        "`!ezloot commands` - Show this help message.\n\n"
        "**Admin Commands:**\n"
        "`!ezloot listusers` - List all registered users.\n"
        "`!ezloot finditem <item>` - Find users with a specified item in their gear (substring matching).\n"
        "`!ezloot assignloot @User <slot>` - Assign loot to a user for a specific gear slot (locks the slot).\n"
        "`!ezloot assignbonusloot @User <slot> <loot>` - Assign bonus loot to a user.\n"
        "`!ezloot unlock @User <slot>` - Unlock a gear slot for a user.\n"
        "`!ezloot removegear @User <slot>` - Reset a gear slot for a user.\n"
        "`!ezloot removeloot @User <slot>` - Remove the loot entry for a specified slot from a user's record.\n"
        "`!ezloot removebonusloot @User <slot>` - Remove the bonus loot entry for a specified slot from a user's record.\n"
        "`!ezloot guildtotal` - Show the total count of loot pieces awarded across all users.\n"
    )
    await ctx.send(help_text)

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
    message_lines = ["**Registered Users:**"]
    for doc in docs:
        data = doc.to_dict()
        user_id = doc.id
        try:
            user = await bot.fetch_user(int(user_id))
            message_lines.append(f"- {user.name} ({user_id})")
        except Exception:
            message_lines.append(f"- Unknown User ({user_id})")
    await ctx.send("\n".join(message_lines))

@bot.command(name="finditem")
@commands.check(is_admin)
async def find_item(ctx, *, item: str):
    """
    Admin: Find users who have recorded a specific item in any gear slot.
    Uses substring matching (case-insensitive) so that partial matches work.
    """
    def fetch_users():
        return list(db.collection("users").stream())
    docs = await asyncio.to_thread(fetch_users)
    found_users = []
    for doc in docs:
        data = doc.to_dict()
        gear = data.get("gear", {})
        for slot_data in gear.values():
            if slot_data.get("item") and item.lower() in slot_data.get("item").strip().lower():
                try:
                    user = await bot.fetch_user(int(doc.id))
                    found_users.append(user.name)
                except Exception:
                    found_users.append(f"UserID {doc.id}")
                break
    if not found_users:
        await ctx.send(f"No users found with item containing **{item}**.")
    else:
        await ctx.send(f"Users with item containing **{item}**: {', '.join(found_users)}")

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
    # use canonical loot entry
    loot_entry = canonical_loot_entry(slot, slot_data['item'])
    await lock_gear_slot(user_id, slot)
    await add_loot(user_id, loot_entry)
    await ctx.send(f"Loot assigned to {user.mention} for **{slot}**: **{slot_data['item']}**.")

@bot.command(name="assignbonusloot")
@commands.check(is_admin)
async def assign_bonusloot(ctx, user: discord.Member, slot: str, *, loot: str):
    """
    Admin: Assign bonus loot to a user.
    The bonus loot entry tracks the slot and loot name.
    Usage: !ezloot assignbonusloot @User <slot> <loot>
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
    bonus_entry = canonical_loot_entry(slot, loot)
    await add_bonusloot(user_id, bonus_entry)
    await ctx.send(f"Bonus loot assigned to {user.mention} for **{slot}**: **{loot}**.")

@bot.command(name="unlock")
@commands.check(is_admin)
async def unlock(ctx, user: discord.Member, slot: str):
    """Admin: Unlock a gear slot for a user."""
    user_id = str(user.id)
    user_data = await get_user(user_id)
    if not user_data:
        await ctx.send(f"{user.mention} is not registered.")
        return
    slot = slot.capitalize()
    if slot not in GEAR_SLOTS:
        await ctx.send(f"{ctx.author.mention}, `{slot}` is not a valid gear slot. Valid slots: {', '.join(GEAR_SLOTS)}")
        return
    await unlock_gear_slot(user_id, slot)
    await ctx.send(f"{user.mention}'s **{slot}** slot has been unlocked.")

@bot.command(name="removegear")
@commands.check(is_admin)
async def remove_gear(ctx, user: discord.Member, slot: str):
    """Admin: Remove the gear item for a specific slot from a user's record (reset it)."""
    user_id = str(user.id)
    user_data = await get_user(user_id)
    if not user_data:
        await ctx.send(f"{user.mention} is not registered.")
        return
    slot = slot.capitalize()
    if slot not in GEAR_SLOTS:
        await ctx.send(f"{ctx.author.mention}, `{slot}` is not a valid gear slot.")
        return
    await remove_gear_item(user_id, slot)
    await ctx.send(f"Gear for slot **{slot}** has been reset for {user.mention}.")

@bot.command(name="removeloot")
@commands.check(is_admin)
async def remove_loot_cmd(ctx, user: discord.Member, slot: str):
    """
    Admin: Remove the loot entry corresponding to a specific slot from a user's record.
    This command finds all loot entries in the 'loot' array that match the canonical format for the given slot.
    """
    user_id = str(user.id)
    user_data = await get_user(user_id)
    if not user_data:
        await ctx.send(f"{user.mention} is not registered.")
        return
    slot = slot.capitalize()
    loot_list = user_data.get("loot", [])
    # use canonical prefix for matching
    prefix = f"{slot}: "
    entries_to_remove = [entry for entry in loot_list if entry.startswith(prefix)]
    if not entries_to_remove:
        await ctx.send(f"No loot entry found for slot **{slot}** in {user.mention}'s record.")
        return
    for entry in entries_to_remove:
        await remove_loot(user_id, entry)
    await ctx.send(f"Loot entry for slot **{slot}** has been removed from {user.mention}'s record.")

@bot.command(name="removebonusloot")
@commands.check(is_admin)
async def remove_bonusloot_cmd(ctx, user: discord.Member, slot: str):
    """
    Admin: Remove the bonus loot entry corresponding to a specific slot from a user's record.
    This command finds all bonus loot entries in the 'bonusloot' array that match the canonical format for the given slot.
    """
    user_id = str(user.id)
    user_data = await get_user(user_id)
    if not user_data:
        await ctx.send(f"{user.mention} is not registered.")
        return
    slot = slot.capitalize()
    bonus_list = user_data.get("bonusloot", [])
    prefix = f"{slot}: "
    entries_to_remove = [entry for entry in bonus_list if entry.startswith(prefix)]
    if not entries_to_remove:
        await ctx.send(f"No bonus loot entry found for slot **{slot}** in {user.mention}'s record.")
        return
    for entry in entries_to_remove:
        await remove_bonusloot(user_id, entry)
    await ctx.send(f"Bonus loot entry for slot **{slot}** has been removed from {user.mention}'s record.")

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
        bonus = data.get("bonusloot", [])
        total_loot += len(loot) + len(bonus)
    await ctx.send(f"The guild has received a total of **{total_loot}** loot pieces.")

# run the bot
bot.run(TOKEN)
