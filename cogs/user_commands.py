# cogs/user_commands.py
import discord
from discord.ext import commands
from utils.db import get_user, register_user, update_gear_item, is_admin
from utils.helpers import resolve_member
from utils.config import GEAR_SLOTS
from utils.logging import log_interaction, format_user

class UserCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="register")
    async def register(self, ctx):
        """Register yourself and then DM for further commands."""
        user_id = str(ctx.author.id)
        user_data = await get_user(user_id)
        if user_data:
            await ctx.send(f"{ctx.author.mention}, you are already registered.")
            return
        success = await register_user(user_id, ctx.author.name)
        if success:
            await ctx.send(f"{ctx.author.mention}, you have been registered! Please DM for further commands.")
            try:
                await ctx.author.send(
                    "Registration successful!\n"
                    "DM Commands:\n"
                    "• `!ezloot set <slot> <item>`\n"
                    "• `!ezloot edit <slot> <new_item>`\n"
                    "• `!ezloot showgear`\n"
                    "• `!ezloot showloot`\n"
                    "• `!ezloot commands`"
                )
            except discord.Forbidden:
                await ctx.send("I couldn't DM you. Enable DMs from server members.")
        else:
            await ctx.send(f"{ctx.author.mention}, registration failed. Please try again.")
            
    def dm_only_check(ctx):
        # admins bypass dm only restriction
        if ctx.guild is not None and not is_admin(ctx):
            raise commands.CheckFailure("User commands must be used in direct messages.")
        return True

    @commands.command(name="set")
    @commands.check(dm_only_check)
    async def set_item(self, ctx, slot: str, *, item: str):
        """Set an item for a given gear slot."""
        user_id = str(ctx.author.id)
        user_data = await get_user(user_id)
        if not user_data:
            await ctx.send("Please register first using !ezloot register in the public channel.")
            return
        slot = slot.capitalize()
        if slot not in GEAR_SLOTS:
            await ctx.send(f"`{slot}` is not a valid gear slot. Valid: {', '.join(GEAR_SLOTS)}")
            return
        gear = user_data.get("gear", {})
        slot_data = gear.get(slot, {})
        if slot_data.get("looted"):
            await ctx.send(f"Your **{slot}** slot is locked as loot has been assigned.")
            return
        if slot_data.get("item") is not None:
            await ctx.send(f"You already have an item for **{slot}**. Use !ezloot edit {slot} <new_item>.")
            return
        await update_gear_item(user_id, slot, item)
        await ctx.send(f"Your **{slot}** has been set to **{item}**.")
        await log_interaction(ctx.author, "set", f"Set {slot} to {item}")

    @commands.command(name="edit")
    @commands.check(dm_only_check)
    async def edit_item(self, ctx, slot: str, *, new_item: str):
        """Edit the recorded item for a given gear slot."""
        user_id = str(ctx.author.id)
        user_data = await get_user(user_id)
        if not user_data:
            await ctx.send("Please register first using !ezloot register in the public channel.")
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
            await ctx.send(f"You do not have an item for **{slot}** yet. Use !ezloot set {slot} <item>.")
            return
        await update_gear_item(user_id, slot, new_item)
        await ctx.send(f"Your **{slot}** has been updated to **{new_item}**.")
        await log_interaction(ctx.author, "edit", f"Updated {slot} to {new_item}")
    
    @commands.command(name="pity")
    @commands.check(dm_only_check)
    async def pity(self, ctx, *, user_identifier: str = None):
        """
        Show your current pity level.
        Admins can supply a user identifier (mention, ID, or username) to see that user's pity level.
        """
        if user_identifier and is_admin(ctx):
            target = await resolve_member(ctx, user_identifier)
            if target is None:
                await ctx.send(f"Could not resolve user '{user_identifier}'. Showing your own pity level instead.")
                target = ctx.author
        else:
            target = ctx.author

        user_id = str(target.id)
        user_data = await get_user(user_id)
        if not user_data:
            await ctx.send(f"{target.mention} is not registered.")
            return
        pity_level = user_data.get("pity", 0)
        
        if target == ctx.author:
            await ctx.send(f"Your pity level is {pity_level}.")
        else:
            await ctx.send(f"{target.name}'s pity level is {pity_level}.")

    @commands.command(name="showgear")
    @commands.check(dm_only_check)
    async def show_gear(self, ctx, *, user_identifier: str = None):
        if user_identifier and ctx.author.guild_permissions.administrator:
            target = await resolve_member(ctx, user_identifier)
            if not target:
                await ctx.send(f"Could not resolve user '{user_identifier}'.")
                return
        else:
            target = ctx.author
        user_id = str(target.id)
        user_data = await get_user(user_id)
        if not user_data:
            await ctx.send(f"{format_user(target)} is not registered.")
            return
        gear = user_data.get("gear", {})
        lines = []
        for slot, data in gear.items():
            item_val = data.get("item", "Not set")
            if data.get("looted"):
                lines.append(f"🔴 **{slot}**: ~~{item_val}~~")
            else:
                lines.append(f"🟢 **{slot}**: {item_val}")
        message = f"**{format_user(target)}'s Gear:**\n" + "\n".join(lines)
        await ctx.send(message)

    @commands.command(name="showloot")
    @commands.check(dm_only_check)
    async def show_loot(self, ctx, *, user_identifier: str = None):
        """
        Show received loot.
        Non-admins see their own loot; admins can specify a user.
        """
        if user_identifier and ctx.author.guild_permissions.administrator:
            target = await resolve_member(ctx, user_identifier)
            if not target:
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
        response_lines.append("")  # blank separator
        if bonus_loot:
            response_lines.append("**Bonus Loot:**")
            response_lines.extend(f"- {entry}" for entry in bonus_loot)
        else:
            response_lines.append("No bonus loot assigned.")
        await ctx.send("\n".join(response_lines))

    @commands.command(name="commands")
    @commands.check(dm_only_check)
    async def user_help(self, ctx):
        """Display a list of all user commands."""
        help_text = (
            "**User Commands (DM only):**\n"
            "`!ezloot register` - Register yourself and then DM for further commands.\n"
            "`!ezloot set <slot> <item>` - Record an item for a gear slot.\n"
            "`!ezloot edit <slot> <new_item>` - Edit the recorded item for a gear slot.\n"
            "`!ezloot showgear` - Display your gear.\n"
            "`!ezloot showloot` - Show your loot.\n"
            "`!ezloot pity` - Show your current pity level.\n"
        )
        await ctx.send(help_text)

async def setup(bot):
    await bot.add_cog(UserCommands(bot))
