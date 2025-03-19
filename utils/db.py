# utils/db.py
import os
import asyncio
import firebase_admin
from firebase_admin import credentials, firestore
from utils.config import FIREBASE_CERTIFICATE, GEAR_SLOTS

if not firebase_admin._apps:
    cred = credentials.Certificate(FIREBASE_CERTIFICATE)
    firebase_admin.initialize_app(cred)

def get_db():
    """Return a Firestore client."""
    return firestore.client()

# global admin ids
ADMIN_IDS = set()

async def load_admin_ids():
    """
    Load admin IDs from Firestore.
    Assumes a document at config/admins with a field "ids" containing an array of IDs.
    """
    global ADMIN_IDS
    db_instance = get_db()
    doc_ref = db_instance.collection("config").document("admins")
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

async def get_user(user_id: str):
    """Retrieve the user document from Firestore."""
    db_instance = get_db()
    doc_ref = db_instance.collection("users").document(user_id)
    doc = await asyncio.to_thread(doc_ref.get)
    if doc.exists:
        return doc.to_dict()
    return None

async def register_user(user_id: str, username: str):
    """Register a new user with default gear, empty loot, and empty bonus loot."""
    db_instance = get_db()
    doc_ref = db_instance.collection("users").document(user_id)
    doc = await asyncio.to_thread(doc_ref.get)
    if doc.exists:
        return False
    data = {
        "username": username,
        "gear": {slot: {"item": None, "looted": False} for slot in GEAR_SLOTS},
        "loot": [],
        "bonusloot": [],
        "pity": 0,
    }
    await asyncio.to_thread(doc_ref.set, data)
    return True

async def update_gear_item(user_id: str, slot: str, item: str):
    """Update the gear item for a given slot."""
    db_instance = get_db()
    doc_ref = db_instance.collection("users").document(user_id)
    await asyncio.to_thread(doc_ref.update, {f"gear.{slot}.item": item})

async def lock_gear_slot(user_id: str, slot: str):
    """Mark a gear slot as locked (loot assigned)."""
    db_instance = get_db()
    doc_ref = db_instance.collection("users").document(user_id)
    await asyncio.to_thread(doc_ref.update, {f"gear.{slot}.looted": True})

async def unlock_gear_slot(user_id: str, slot: str):
    """Unlock a gear slot (mark loot as not assigned)."""
    db_instance = get_db()
    doc_ref = db_instance.collection("users").document(user_id)
    await asyncio.to_thread(doc_ref.update, {f"gear.{slot}.looted": False})

async def add_loot(user_id: str, loot_entry: str):
    """Add a loot entry to the user's record using Firestore's ArrayUnion."""
    db_instance = get_db()
    doc_ref = db_instance.collection("users").document(user_id)
    await asyncio.to_thread(doc_ref.update, {"loot": firestore.ArrayUnion([loot_entry])})

async def add_bonusloot(user_id: str, bonusloot_entry: str):
    """Add a bonus loot entry to the user's record using Firestore's ArrayUnion."""
    db_instance = get_db()
    doc_ref = db_instance.collection("users").document(user_id)
    await asyncio.to_thread(doc_ref.update, {"bonusloot": firestore.ArrayUnion([bonusloot_entry])})

async def remove_gear_item(user_id: str, slot: str):
    """Remove the gear item for a given slot (reset it to None and unlock it)."""
    db_instance = get_db()
    doc_ref = db_instance.collection("users").document(user_id)
    await asyncio.to_thread(doc_ref.update, {f"gear.{slot}.item": None, f"gear.{slot}.looted": False})

async def remove_loot(user_id: str, loot_entry: str):
    """Remove a loot entry from the user's record using Firestore's ArrayRemove."""
    db_instance = get_db()
    doc_ref = db_instance.collection("users").document(user_id)
    await asyncio.to_thread(doc_ref.update, {"loot": firestore.ArrayRemove([loot_entry])})

async def remove_bonusloot(user_id: str, bonusloot_entry: str):
    """Remove a bonus loot entry from the user's record using Firestore's ArrayRemove."""
    db_instance = get_db()
    doc_ref = db_instance.collection("users").document(user_id)
    await asyncio.to_thread(doc_ref.update, {"bonusloot": firestore.ArrayRemove([bonusloot_entry])})
    
async def add_pity(user_id: str):
    """Increment the pity level for a user by 1."""
    db_instance = get_db()
    doc_ref = db_instance.collection("users").document(user_id)
    await asyncio.to_thread(doc_ref.update, {"pity": firestore.Increment(1)})
    
async def set_pity(user_id: str, value: int):
    """Set the pity level for a user to a specific value."""
    db_instance = get_db()
    doc_ref = db_instance.collection("users").document(user_id)
    await asyncio.to_thread(doc_ref.update, {"pity": value})
