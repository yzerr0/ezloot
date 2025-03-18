# utils/helpers.py
import asyncio
import discord
from discord.ext import commands
from utils.db import get_db

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
            db = get_db()
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
                        member = await ctx.bot.fetch_user(int(doc.id))
                        if member is not None:
                            return member
                    except Exception:
                        pass
        return None
    else:
        if identifier.isdigit():
            try:
                member = await ctx.bot.fetch_user(int(identifier))
                return member
            except Exception:
                return None
        return None
