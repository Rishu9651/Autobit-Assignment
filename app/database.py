from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings
import asyncio


class Database:
    client: AsyncIOMotorClient = None
    database = None


db = Database()


async def get_database():
    return db.database

 #Create database connection
async def connect_to_mongo():
   
    db.client = AsyncIOMotorClient(settings.mongodb_url)
    db.database = db.client[settings.mongodb_database]
    
    # Create indexes
    await create_indexes()

#Close database connection
async def close_mongo_connection():
    
    if db.client:
        db.client.close()

# Create database indexes 
async def create_indexes():
    # Users collection indexes
    await db.database.users.create_index("email", unique=True)
    await db.database.users.create_index("provider_id")
    
    # Servers collection indexes
    await db.database.servers.create_index("user_id")
    await db.database.servers.create_index("container_id")
    
    # Usage samples collection indexes
    await db.database.usage_samples.create_index([("server_id", 1), ("ts", 1)])
    await db.database.usage_samples.create_index("ts")
    
    # Invoices collection indexes
    await db.database.invoices.create_index("user_id")
    await db.database.invoices.create_index([("period_start", 1), ("period_end", 1)])
    
    # Transactions collection indexes
    await db.database.transactions.create_index("invoice_id")
    await db.database.transactions.create_index("ts")
