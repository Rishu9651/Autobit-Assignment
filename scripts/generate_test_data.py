#!/usr/bin/env python3
"""
Test data generation script for AutoBit Backend
Generates sample usage data and invoices for testing
"""

import asyncio
import random
from datetime import datetime, timedelta
from app.database import connect_to_mongo, get_database
from app.models import UsageSample
import uuid


async def generate_test_usage_data():
    """Generate test usage data for existing servers"""
    await connect_to_mongo()
    db = await get_database()
    
    # Get all servers
    servers = []
    async for server_doc in db.servers.find():
        servers.append(server_doc)
    
    if not servers:
        print("No servers found. Please create some servers first.")
        return
    
    print(f"Generating test data for {len(servers)} servers...")
    
    # Generate usage data for the last 7 days
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=7)
    
    # Generate samples every 30 seconds
    current_time = start_time
    sample_count = 0
    
    while current_time < end_time:
        for server in servers:
            # Generate realistic usage data
            cpu_pct = random.uniform(10, 80)  # 10-80% CPU usage
            ram_mib = random.uniform(server["ram_gib"] * 1024 * 0.3, server["ram_gib"] * 1024 * 0.9)  # 30-90% of allocated RAM
            disk_gb = random.uniform(server["disk_gib"] * 0.1, server["disk_gib"] * 0.7)  # 10-70% of allocated disk
            
            sample = UsageSample(
                server_id=server["id"],
                ts=current_time,
                cpu_pct=round(cpu_pct, 2),
                ram_mib=round(ram_mib, 2),
                disk_gib=round(disk_gb, 2)
            )
            
            await db.usage_samples.insert_one(sample.dict())
            sample_count += 1
        
        # Move to next sample time (30 seconds later)
        current_time += timedelta(seconds=30)
    
    print(f"Generated {sample_count} usage samples")
    print(f"Time range: {start_time} to {end_time}")


async def create_test_user():
    """Create a test user if none exists"""
    await connect_to_mongo()
    db = await get_database()
    
    # Check if any users exist
    user_count = await db.users.count_documents({})
    
    if user_count == 0:
        from app.auth import get_password_hash
        
        test_user = {
            "id": str(uuid.uuid4()),
            "email": "test@example.com",
            "name": "Test User",
            "provider": "email",
            "provider_id": None,
            "password_hash": get_password_hash("testpassword123"),
            "created_at": datetime.utcnow()
        }
        
        await db.users.insert_one(test_user)
        print("Created test user: test@example.com / testpassword123")
        return test_user
    else:
        print(f"Found {user_count} existing users")
        return None


async def create_test_server():
    """Create a test server if none exists"""
    await connect_to_mongo()
    db = await get_database()
    
    # Check if any servers exist
    server_count = await db.servers.count_documents({})
    
    if server_count == 0:
        # Get first user
        user = await db.users.find_one()
        if not user:
            print("No users found. Please create a user first.")
            return None
        
        test_server = {
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "name": "Test Server",
            "image": "nginx:alpine",
            "cpu_limit": 0.5,
            "cores": 1,
            "ram_gib": 1.0,
            "disk_gib": 10.0,
            "status": "running",
            "container_id": f"test-container-{uuid.uuid4()}",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        await db.servers.insert_one(test_server)
        print("Created test server: Test Server")
        return test_server
    else:
        print(f"Found {server_count} existing servers")
        return None


async def main():
    """Main function to generate test data"""
    print("AutoBit Test Data Generator")
    print("=" * 40)
    
    # Create test user if needed
    await create_test_user()
    
    # Create test server if needed
    await create_test_server()
    
    # Generate usage data
    await generate_test_usage_data()
    
    print("\nTest data generation complete!")
    print("\nYou can now:")
    print("1. Login with test@example.com / testpassword123")
    print("2. View usage data for your servers")
    print("3. Generate invoices for the test period")
    print("4. Test the weekly email functionality")


if __name__ == "__main__":
    asyncio.run(main())
