# cogs/admin_commands.py
from discord.ext import commands
import asyncio

from utils.db import get_user, lock_gear_slot, unlock_gear_slot, add_loot, add_bonusloot, add_pity, remove_gear_item, remove_loot, remove_bonusloot, is_admin, ADMIN_IDS, get_db
from utils.helpers import canonical_loot_entry, resolve_member
from utils.config import GEAR_SLOTS
from utils.logging import log_interaction

class AdminCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    async def cog_check(self, ctx):
        return is_admin(ctx)

    @commands.command(name="listusers")
    async def list_users(self, ctx):
        """Admin: List all registered users."""
        def fetch_users():
            db = get_db()
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
                user = await self.bot.fetch_user(int(doc.id))
                message_lines.append(f"- {user.name} ({user_id})")
            except Exception:
                message_lines.append(f"- Unknown User ({user_id})")
        await ctx.send("\n".join(message_lines))

    @commands.command(name="finditem")
    async def find_item(self, ctx, *, item: str):
        """
        Admin: Find users who have recorded a specific item in any gear slot.
        Uses substring matching (case-insensitive) so that partial matches work.
        Displays each user's name along with the gear slot, full item name, and its locked status.
        """
        def fetch_users():
            db = get_db()
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
                    user = await self.bot.fetch_user(int(doc.id))
                    results.append(f"{user.name} - " + ", ".join(matches))
                except Exception:
                    results.append(f"UserID {doc.id} - " + ", ".join(matches))
        if not results:
            await ctx.send(f"No users found with item containing **{item}**.")
        else:
            await ctx.send("Matches found:\n" + "\n".join(results))

    @commands.command(name="findbonusloot")
    async def find_bonusloot(self, ctx, *, item: str):
        """
        Admin: Find users who have a bonus loot entry containing a specific string.
        Uses substring matching (case-insensitive) and displays each user's name along with matching bonus loot entries.
        """
        def fetch_users():
            db = get_db()
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
                    user = await self.bot.fetch_user(int(doc.id))
                    results.append(f"{user.name} - " + ", ".join(matches))
                except Exception:
                    results.append(f"UserID {doc.id} - " + ", ".join(matches))
        if not results:
            await ctx.send(f"No users found with bonus loot containing **{item}**.")
        else:
            await ctx.send("Matches found:\n" + "\n".join(results))

    @commands.command(name="assignloot")
    async def assign_loot(self, ctx, user_identifier: str, slot: str):
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

    @commands.command(name="assignbonusloot")
    async def assign_bonusloot(self, ctx, user_identifier: str, slot: str, *, loot: str):
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
        
    @commands.command(name="addpity")
    async def add_pity_command(self, ctx, user_identifier: str):
        """
        Admin: Increment the pity level for a user by 1.
        Usage: !ezloot addpity <user_identifier>
        """
        member = await resolve_member(ctx, user_identifier)
        if member is None:
            await ctx.send(f"Could not resolve user '{user_identifier}'.")
            return
        user_id = str(member.id)
        await add_pity(user_id)
        user_data = await get_user(user_id)
        new_pity = user_data.get("pity", 0)
        await ctx.send(f"Pity level for {member.mention} has been incremented to {new_pity}.")
        await log_interaction(ctx.author, "addpity", f"Incremented pity for {member.name} to {new_pity}")


    @commands.command(name="unlock")
    async def unlock(self, ctx, user_identifier: str, slot: str):
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

    @commands.command(name="removegear")
    async def remove_gear(self, ctx, user_identifier: str, slot: str):
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

    @commands.command(name="removeloot")
    async def remove_loot_cmd(self, ctx, user_identifier: str, slot: str):
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

    @commands.command(name="removebonusloot")
    async def remove_bonusloot(self, ctx, user_identifier: str, slot: str):
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

    @commands.command(name="removeuser")
    async def remove_user(self, ctx, user_identifier: str):
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
        
        if member.id in ADMIN_IDS or (hasattr(member, 'guild_permissions') and member.guild_permissions.administrator):
            await ctx.send("Cannot remove an administrator from the database.")
            return

        user_id = str(member.id)
        db = get_db()
        doc_ref = db.collection("users").document(user_id)
        doc = await asyncio.to_thread(doc_ref.get)
        if not doc.exists:
            await ctx.send(f"{member.mention} is not registered in the database.")
            return
        await asyncio.to_thread(doc_ref.delete)
        await ctx.send(f"User {member.mention} has been removed from the database.")
        await log_interaction(ctx.author, "removeuser", f"Removed user {member.name} ({user_id}) from the database.")

    @commands.command(name="guildtotal")
    async def guild_total(self, ctx):
        """Admin: Show the total count of loot pieces awarded across all users."""
        def fetch_users():
            from utils.db import db
            return list(db.collection("users").stream())
        docs = await asyncio.to_thread(fetch_users)
        total_loot = 0
        for doc in docs:
            data = doc.to_dict()
            loot = data.get("loot", [])
            bonus = data.get("bonusloot", [])
            total_loot += len(loot) + len(bonus)
        await ctx.send(f"The guild has received a total of **{total_loot}** loot pieces.")

    @commands.command(name="admincommands")
    async def admin_help(self, ctx):
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

async def setup(bot):
    await bot.add_cog(AdminCommands(bot))
