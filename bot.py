import os
import json
import discord
from discord.ext import commands
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore
import asyncio
import datetime

# load env & firebase credentials
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN is None:
    raise ValueError("Missing discord token.")

FIREBASE_CERTIFICATE = os.getenv("FIREBASE_CERTIFICATE")
if FIREBASE_CERTIFICATE is None:
    raise ValueError("Missing FIREBASE_CERTIFICATE path.")

# initialize firebase
cred = credentials.Certificate(FIREBASE_CERTIFICATE)
firebase_admin.initialize_app(cred)
db = firestore.client()

# bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!ezdev ", intents=intents)
bot.remove_command("help")

GEAR_SLOTS = ["Head", "Cloak", "Chest", "Gloves", "Legs", "Boots", "Necklace", "Belt", "Ring1", "Ring2", "Weapon1", "Weapon2"]

# global admin ids
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
    """Check if the invoking user is an admin by ID or has guild administrator permissions."""
    return ctx.author.id in ADMIN_IDS or (ctx.guild is not None and ctx.author.guild_permissions.administrator)

# logging functions
INTERACTION_LOGS = []

async def log_interaction(user, command_name, details):
    """Log an interaction with a timestamp, the user, command name, and details."""
    timestamp = datetime.datetime.now().isoformat()
    log_entry = f"[{timestamp}] {user} used {command_name}: {details}"
    INTERACTION_LOGS.append(log_entry)

async def send_logs_periodically():
    """Periodically send accumulated logs to a designated channel."""
    await bot.wait_until_ready()
    log_channel_id = os.getenv("LOG_CHANNEL_ID")
    if log_channel_id is None:
        print("LOG_CHANNEL_ID not set; skipping periodic log posting.")
        return
    log_channel_id = int(log_channel_id)
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
        await asyncio.sleep(300)  # posts logs every 5 minutes

@bot.event
async def setup_hook():
    await load_admin_ids()
    asyncio.create_task(send_logs_periodically())

# helper functions
def canonical_loot_entry(slot: str, item: str) -> str:
    """
    Generate a canonical loot entry.
    Ensures the slot is capitalized and the item is lowercased and stripped of extra spaces.
    Format: "Slot: item"
    """
    return f"{slot.strip().capitalize()}: {item.strip().lower()}"

def normalize_item(item: str) -> str:
    return item.strip().lower()

async def resolve_member(ctx, identifier: str) -> discord.Member:
    """
    Resolve a guild member from an identifier (mention, user ID, or username).

    In a guild channel:
      1. Try using MemberConverter (handles mentions and numeric IDs).
      2. If that fails, iterate through guild members to match on name or display_name.
      3. If still not found, iterate over the Firestore "users" collection to find a document
         whose "username" property matches (case-insensitive) and fetch that member by the document ID.

    In a DM (ctx.guild is None), only numeric IDs or mentions can be resolved via bot.fetch_user.
    """
    member = None
    if ctx.guild is not None:
        try:
            member = await commands.MemberConverter().convert(ctx, identifier)
            if member is not None:
                return member
        except commands.BadArgument:
            pass
        identifier_lower = identifier.lower()
        member = discord.utils.find(
            lambda m: m.name.lower() == identifier_lower or m.display_name.lower() == identifier_lower,
            ctx.guild.members
        )
        if member is not None:
            return member
        def fetch_all_users():
            return list(db.collection("users").stream())
        docs = await asyncio.to_thread(fetch_all_users)
        for doc in docs:
            data = doc.to_dict()
            if "username" in data and data["username"].strip().lower() == identifier_lower:
                try:
                    member = await ctx.guild.fetch_member(int(doc.id))
                    if member is not None:
                        return member
                except Exception:
                    try:
                        member = await bot.fetch_user(int(doc.id))
                        if member is not None:
                            return member
                    except Exception:
                        pass
        return None
    else:
        if identifier.isdigit():
            try:
                member = await bot.fetch_user(int(identifier))
                return member
            except Exception:
                return None
        return None

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

# bot event handlers    
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

# register to initiate private message relay
@bot.command(name="register")
async def register(ctx):
    """Register yourself (publicly) to initialize your gear in the database.
    After registration, please DM me for further commands."""
    user_id = str(ctx.author.id)
    user_data = await get_user(user_id)
    if user_data:
        await ctx.send(f"{ctx.author.mention}, you are already registered.")
        return
    success = await register_user(user_id, ctx.author.name)
    if success:
        await ctx.send(f"{ctx.author.mention}, you have been registered! Please DM me for further commands (set, edit, showgear, etc.).")
        try:
            await ctx.author.send(
                "Registration successful!\n"
                "You can now use the following DM commands:\n"
                "• `!ezloot set <slot> <item>` – Record an item for a gear slot.\n"
                "• `!ezloot edit <slot> <new_item>` – Edit an item for a gear slot.\n"
                "• `!ezloot showgear` – Display your gear.\n"
                "• `!ezloot showloot` – Show your loot.\n"
                "Type `!ezloot commands` for a list of user commands."
            )
        except discord.Forbidden:
            await ctx.send("I couldn't DM you. Please enable DMs from server members so I can send you further instructions.")
    else:
        await ctx.send(f"{ctx.author.mention}, registration failed. Please try again.")

def dm_only_check(ctx):
    # admins bypass dm only restriction
    if ctx.guild is not None and not is_admin(ctx):
        raise commands.CheckFailure("User commands must be used in direct messages.")
    return True

@bot.command(name="set")
@commands.check(dm_only_check)
async def set_item(ctx, slot: str, *, item: str):
    """(DM only for non-admins) Set an item for a given gear slot."""
    user_id = str(ctx.author.id)
    user_data = await get_user(user_id)
    if not user_data:
        await ctx.send("Please register first using `!ezloot register` in the public channel.")
        return
    slot = slot.capitalize()
    if slot not in GEAR_SLOTS:
        await ctx.send(f"`{slot}` is not a valid gear slot. Valid slots: {', '.join(GEAR_SLOTS)}")
        return
    gear = user_data.get("gear", {})
    slot_data = gear.get(slot, {})
    if slot_data.get("looted"):
        await ctx.send(f"Your **{slot}** slot is locked as loot has already been assigned.")
        return
    if slot_data.get("item") is not None:
        await ctx.send(f"You already have an item recorded for **{slot}**. Use `!ezloot edit {slot} <new_item>` to change it.")
        return
    await update_gear_item(user_id, slot, item)
    await ctx.send(f"Your **{slot}** has been set to **{item}**.")
    await log_interaction(ctx.author, "set", f"Set {slot} to {item}")

@bot.command(name="edit")
@commands.check(dm_only_check)
async def edit_item(ctx, slot: str, *, new_item: str):
    """(DM only for non-admins) Edit the recorded item for a given gear slot."""
    user_id = str(ctx.author.id)
    user_data = await get_user(user_id)
    if not user_data:
        await ctx.send("Please register first using `!ezloot register` in the public channel.")
        return
    slot = slot.capitalize()
    if slot not in GEAR_SLOTS:
        await ctx.send(f"`{slot}` is not a valid gear slot.")
        return
    gear = user_data.get("gear", {})
    slot_data = gear.get(slot, {})
    if slot_data.get("looted"):
        await ctx.send(f"You cannot change **{slot}** because loot has been assigned.")
        return
    if slot_data.get("item") is None:
        await ctx.send(f"You do not have an item set for **{slot}** yet. Use `!ezloot set {slot} <item>` to set it first.")
        return
    await update_gear_item(user_id, slot, new_item)
    await ctx.send(f"Your **{slot}** has been updated to **{new_item}**.")
    await log_interaction(ctx.author, "edit", f"Updated {slot} to {new_item}")

@bot.command(name="showgear")
@commands.check(dm_only_check)
async def show_gear(ctx, *, user_identifier: str = None):
    """
    Display gear.
    - Non-admins: shows your own gear.
    - Admins: if you supply a user identifier (mention, user ID, or username),
      this command will display that user's gear.
    """
    if user_identifier and is_admin(ctx):
        target = await resolve_member(ctx, user_identifier)
        if target is None:
            await ctx.send(f"Could not resolve user '{user_identifier}'.")
            return
    else:
        target = ctx.author

    user_id = str(target.id)
    user_data = await get_user(user_id)
    if not user_data:
        await ctx.send(f"{target.mention} is not registered.")
        return

    gear = user_data.get("gear", {})
    # Build the formatted gear lines.
    lines = [f"**{slot}**: {data.get('item', 'Not set')} — {'Locked' if data.get('looted') else 'Unlocked'}" 
             for slot, data in gear.items()]
    message = f"**{target.name}'s Gear:**\n" + "\n".join(lines)
    await ctx.send(message)


@bot.command(name="showloot")
@commands.check(dm_only_check)
async def show_loot(ctx, *, user_identifier: str = None):
    """
    (DM only for non-admins) Show received loot.
    - If no user identifier is provided, show your loot.
    - If you are an admin and supply a user identifier (mention, user ID, or username),
      attempt to resolve and show that user's loot.
    """
    if user_identifier and is_admin(ctx):
        target = await resolve_member(ctx, user_identifier)
        if target is None:
            await ctx.send(f"Could not resolve user '{user_identifier}'.")
            return
    else:
        target = ctx.author

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
@commands.check(dm_only_check)
async def user_help(ctx):
    """(DM only for non-admins) Display a list of all user commands."""
    help_text = (
        "**User Commands (DM only):**\n"
        "`!ezloot register` - Register yourself (publicly) and then DM me for further commands.\n"
        "`!ezloot set <slot> <item>` - Record an item for a specific gear slot.\n"
        "`!ezloot edit <slot> <new_item>` - Edit the recorded item for a specific gear slot.\n"
        "`!ezloot showgear` - Display your currently recorded gear.\n"
        "`!ezloot showloot` - Show loot for yourself.\n"
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
            user = await bot.fetch_user(int(doc.id))
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
    Displays each user's name along with the gear slot, full item name, and its locked status.
    """
    def fetch_users():
        return list(db.collection("users").stream())
    docs = await asyncio.to_thread(fetch_users)
    results = []
    search_term = item.strip().lower()
    for doc in docs:
        data = doc.to_dict()
        gear = data.get("gear", {})
        matches = []
        for slot, slot_data in gear.items():
            item_value = slot_data.get("item")
            if item_value and search_term in item_value.strip().lower():
                status = "Locked" if slot_data.get("looted") else "Unlocked"
                matches.append(f"{slot} ({status}): {item_value.strip()}")
        if matches:
            try:
                user = await bot.fetch_user(int(doc.id))
                results.append(f"{user.name} - " + ", ".join(matches))
            except Exception:
                results.append(f"UserID {doc.id} - " + ", ".join(matches))
    if not results:
        await ctx.send(f"No users found with item containing **{item}**.")
    else:
        await ctx.send("Matches found:\n" + "\n".join(results))
       
@bot.command(name="findbonusloot")
@commands.check(is_admin)
async def find_bonusloot(ctx, *, item: str):
    """
    Admin: Find users who have a bonus loot entry containing a specific string.
    Uses substring matching (case-insensitive) and displays each user's name along with matching bonus loot entries.
    """
    def fetch_users():
        return list(db.collection("users").stream())
    docs = await asyncio.to_thread(fetch_users)
    results = []
    search_term = item.strip().lower()
    for doc in docs:
        data = doc.to_dict()
        bonus_list = data.get("bonusloot", [])
        matches = []
        for entry in bonus_list:
            if search_term in entry.strip().lower():
                matches.append(entry.strip())
        if matches:
            try:
                user = await bot.fetch_user(int(doc.id))
                results.append(f"{user.name} - " + ", ".join(matches))
            except Exception:
                results.append(f"UserID {doc.id} - " + ", ".join(matches))
    if not results:
        await ctx.send(f"No users found with bonus loot containing **{item}**.")
    else:
        await ctx.send("Matches found:\n" + "\n".join(results))


@bot.command(name="assignloot")
@commands.check(is_admin)
async def assign_loot(ctx, user_identifier: str, slot: str):
    """
    Admin: Assign loot to a user based on one of their recorded gear items.
    Once assigned, that gear slot becomes locked.
    Usage: !ezloot assignloot <user_identifier> <slot>
    (User identifier can be a mention, user ID, or username.)
    """
    member = await resolve_member(ctx, user_identifier)
    if member is None:
        await ctx.send(f"Could not resolve user '{user_identifier}'.")
        return
    user_id = str(member.id)
    user_data = await get_user(user_id)
    if not user_data:
        await ctx.send(f"{member.mention} is not registered.")
        return
    slot = slot.capitalize()
    if slot not in GEAR_SLOTS:
        await ctx.send(f"{ctx.author.mention}, `{slot}` is not a valid gear slot. Valid slots: {', '.join(GEAR_SLOTS)}")
        return
    gear = user_data.get("gear", {})
    slot_data = gear.get(slot, {})
    if slot_data.get("item") is None:
        await ctx.send(f"{member.mention} does not have an item set for **{slot}**.")
        return
    if slot_data.get("looted"):
        await ctx.send(f"{member.mention}'s **{slot}** item has already been awarded.")
        return
    loot_entry = canonical_loot_entry(slot, slot_data['item'])
    await lock_gear_slot(user_id, slot)
    await add_loot(user_id, loot_entry)
    await ctx.send(f"Loot assigned to {member.mention} for **{slot}**: **{slot_data['item']}**.")
    await log_interaction(ctx.author, "assignloot", f"Assigned loot for {member.name} ({slot}: {slot_data['item']})")

@bot.command(name="assignbonusloot")
@commands.check(is_admin)
async def assign_bonusloot(ctx, user_identifier: str, slot: str, *, loot: str):
    """
    Admin: Assign bonus loot to a user.
    Usage: !ezloot assignbonusloot <user_identifier> <slot> <loot>
    """
    member = await resolve_member(ctx, user_identifier)
    if member is None:
        await ctx.send(f"Could not resolve user '{user_identifier}'.")
        return
    user_id = str(member.id)
    user_data = await get_user(user_id)
    if not user_data:
        await ctx.send(f"{member.mention} is not registered.")
        return
    slot = slot.capitalize()
    if slot not in GEAR_SLOTS:
        await ctx.send(f"{ctx.author.mention}, `{slot}` is not a valid gear slot. Valid slots: {', '.join(GEAR_SLOTS)}")
        return
    bonus_entry = canonical_loot_entry(slot, loot)
    await add_bonusloot(user_id, bonus_entry)
    await ctx.send(f"Bonus loot assigned to {member.mention} for **{slot}**: **{loot}**.")
    await log_interaction(ctx.author, "assignbonusloot", f"Assigned bonus loot for {member.name} ({slot}: {loot})")

@bot.command(name="unlock")
@commands.check(is_admin)
async def unlock(ctx, user_identifier: str, slot: str):
    """Admin: Unlock a gear slot for a user."""
    member = await resolve_member(ctx, user_identifier)
    if member is None:
        await ctx.send(f"Could not resolve user '{user_identifier}'.")
        return
    user_id = str(member.id)
    user_data = await get_user(user_id)
    if not user_data:
        await ctx.send(f"{member.mention} is not registered.")
        return
    slot = slot.capitalize()
    if slot not in GEAR_SLOTS:
        await ctx.send(f"{ctx.author.mention}, `{slot}` is not a valid gear slot. Valid slots: {', '.join(GEAR_SLOTS)}")
        return
    await unlock_gear_slot(user_id, slot)
    await ctx.send(f"{member.mention}'s **{slot}** slot has been unlocked.")
    await log_interaction(ctx.author, "unlock", f"Unlocked {member.name}'s {slot} slot")

@bot.command(name="removegear")
@commands.check(is_admin)
async def remove_gear(ctx, user_identifier: str, slot: str):
    """Admin: Reset the gear item for a specific slot for a user."""
    member = await resolve_member(ctx, user_identifier)
    if member is None:
        await ctx.send(f"Could not resolve user '{user_identifier}'.")
        return
    user_id = str(member.id)
    user_data = await get_user(user_id)
    if not user_data:
        await ctx.send(f"{member.mention} is not registered.")
        return
    slot = slot.capitalize()
    if slot not in GEAR_SLOTS:
        await ctx.send(f"{ctx.author.mention}, `{slot}` is not a valid gear slot.")
        return
    await remove_gear_item(user_id, slot)
    await ctx.send(f"Gear for slot **{slot}** has been reset for {member.mention}.")
    await log_interaction(ctx.author, "removegear", f"Removed gear for {member.name} ({slot})")

@bot.command(name="removeloot")
@commands.check(is_admin)
async def remove_loot_cmd(ctx, user_identifier: str, slot: str):
    """
    Admin: Remove the loot entry corresponding to a specific slot from a user's record.
    """
    member = await resolve_member(ctx, user_identifier)
    if member is None:
        await ctx.send(f"Could not resolve user '{user_identifier}'.")
        return
    user_id = str(member.id)
    user_data = await get_user(user_id)
    if not user_data:
        await ctx.send(f"{member.mention} is not registered.")
        return
    slot = slot.capitalize()
    loot_list = user_data.get("loot", [])
    prefix = f"{slot}: "
    entries_to_remove = [entry for entry in loot_list if entry.startswith(prefix)]
    if not entries_to_remove:
        await ctx.send(f"No loot entry found for slot **{slot}** in {member.mention}'s record.")
        return
    for entry in entries_to_remove:
        await remove_loot(user_id, entry)
    await ctx.send(f"Loot entry for slot **{slot}** has been removed from {member.mention}'s record.")
    await log_interaction(ctx.author, "removeloot", f"Removed loot for {member.name} ({slot})")

@bot.command(name="removebonusloot")
@commands.check(is_admin)
async def remove_bonusloot_cmd(ctx, user_identifier: str, slot: str):
    """
    Admin: Remove the bonus loot entry corresponding to a specific slot from a user's record.
    """
    member = await resolve_member(ctx, user_identifier)
    if member is None:
        await ctx.send(f"Could not resolve user '{user_identifier}'.")
        return
    user_id = str(member.id)
    user_data = await get_user(user_id)
    if not user_data:
        await ctx.send(f"{member.mention} is not registered.")
        return
    slot = slot.capitalize()
    bonus_list = user_data.get("bonusloot", [])
    prefix = f"{slot}: "
    entries_to_remove = [entry for entry in bonus_list if entry.startswith(prefix)]
    if not entries_to_remove:
        await ctx.send(f"No bonus loot entry found for slot **{slot}** in {member.mention}'s record.")
        return
    for entry in entries_to_remove:
        await remove_bonusloot(user_id, entry)
    await ctx.send(f"Bonus loot entry for slot **{slot}** has been removed from {member.mention}'s record.")
    await log_interaction(ctx.author, "removebonusloot", f"Removed bonus loot for {member.name} ({slot})")
    
@bot.command(name="removeuser")
@commands.check(is_admin)
async def remove_user(ctx, user_identifier: str):
    """
    Admin: Remove a user from the database (non-admin users only).
    Usage: !ezdev removeuser <user_identifier>
    (User identifier can be a mention, user ID, or username.)
    
    This command will not remove users that are recognized as administrators.
    """
    member = await resolve_member(ctx, user_identifier)
    if member is None:
        await ctx.send(f"Could not resolve user '{user_identifier}'.")
        return

    # prevents removal of administrators
    if member.id in ADMIN_IDS or (ctx.guild is not None and member.guild_permissions.administrator):
        await ctx.send("Cannot remove an administrator from the database.")
        return

    user_id = str(member.id)
    doc_ref = db.collection("users").document(user_id)
    doc = await asyncio.to_thread(doc_ref.get)
    if not doc.exists:
        await ctx.send(f"{member.mention} is not registered in the database.")
        return
    await asyncio.to_thread(doc_ref.delete)
    await ctx.send(f"User {member.mention} has been removed from the database.")
    await log_interaction(ctx.author, "removeuser", f"Removed user {member.name} ({user_id}) from the database.")

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

@bot.command(name="admincommands")
@commands.check(is_admin)
async def admin_help(ctx):
    """Admin: Display a list of all admin commands."""
    help_text = (
        "**Admin Commands:**\n"
        "`!ezloot listusers` - List all registered users.\n"
        "`!ezloot finditem <item>` - Find users with a specified item in their gear (substring matching) and display lock status.\n"
        "`!ezloot findbonusloot <item>` - Find users with bonus loot entries containing a specified string.\n"
        "`!ezloot assignloot <user_identifier> <slot>` - Assign loot to a user for a specific gear slot (locks the slot).\n"
        "`!ezloot assignbonusloot <user_identifier> <slot> <loot>` - Assign bonus loot to a user.\n"
        "`!ezloot unlock <user_identifier> <slot>` - Unlock a gear slot for a user.\n"
        "`!ezloot removegear <user_identifier> <slot>` - Reset a gear slot for a user.\n"
        "`!ezloot removeloot <user_identifier> <slot>` - Remove the loot entry for a specified slot from a user's record.\n"
        "`!ezloot removebonusloot <user_identifier> <slot>` - Remove the bonus loot entry for a specified slot from a user's record.\n"
        "`!ezloot removeuser <user_identifier>` - Remove a user from the database (non-admin users only).\n"
        "`!ezloot guildtotal` - Show the total count of loot pieces awarded across all users.\n"
        "`!ezloot admincommands` - Show this help message.\n"
    )
    await ctx.send(help_text)

# start bot
bot.run(TOKEN)
