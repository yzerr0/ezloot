# utils/config.py
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
FIREBASE_CERTIFICATE = os.getenv("FIREBASE_CERTIFICATE")
LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID")

GEAR_SLOTS = [
    "Head", "Cloak", "Chest", "Gloves", "Legs", "Boots", "Necklace", 
    "Bracelet", "Belt", "Ring1", "Ring2", "Weapon1", "Weapon2"
]
