import os
import motor.motor_asyncio
from dotenv import load_dotenv

load_dotenv()

client = motor.motor_asyncio.AsyncIOMotorClient(
    os.getenv("MONGO_URL")
)

database = client["cinema_db"]

director_collection = database["directors"]
movie_collection = database["movies"]
room_collection = database["rooms"]
session_collection = database["sessions"]
payment_collection = database["payments"]
ticket_collection = database["tickets"]