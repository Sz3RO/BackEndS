from motor.motor_asyncio import AsyncIOMotorClient
import requests
import motor.motor_asyncio
import asyncio

from datetime import datetime
MONGO_URL = "mongodb+srv://CPL_FE_06_GR6:CPL_FE_06_GR6@cluster0.8euhvjw.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

client = AsyncIOMotorClient(MONGO_URL)
db = client.fashionDB
