# app/config/db.py
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
mongodb_db = os.getenv("MONGODB_DB", "openhands_telemetry")

client = AsyncIOMotorClient(mongodb_uri)
db = client[mongodb_db]

telemetry_collection = db.telemetry_events