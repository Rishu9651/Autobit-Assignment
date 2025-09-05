import asyncio
import logging
import uuid
from datetime import datetime
from app.database import connect_to_mongo, get_database
from app.docker_manager import docker_manager
from app.nats_client import nats_client, publish_usage_sampled
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def sample_server_usage(server_id: str, container_id: str, db):
    try:
    
        is_running = await docker_manager.is_container_running(container_id)
        if not is_running:
            logger.warning(f"Container {container_id} for server {server_id} is not running or does not exist. Removing server from DB.")
            await db.servers.delete_one({"id": server_id})
            return
        
        stats = await docker_manager.get_container_stats(container_id)
        if stats:
    
            sample = {
                "id": str(uuid.uuid4()),
                "server_id": server_id,
                "ts": datetime.utcnow(),
                "cpu_pct": stats["cpu_percent"],
                "ram_mib": stats["memory_mb"],
                "disk_gib": stats["disk_gb"]
            }
      
            await db.usage_samples.insert_one(sample)

            await publish_usage_sampled(server_id, sample["ts"].isoformat())
            
            logger.info(f"Sampled usage for server {server_id}: CPU={stats['cpu_percent']}%, RAM={stats['memory_mb']}MB")
        else:
            logger.warning(f"Failed to get stats for server {server_id}")
            
    except Exception as e:
        logger.error(f"Error sampling usage for server {server_id}: {e}")


async def usage_sampling_loop():
    logger.info("Starting usage sampling worker...")
    
    await connect_to_mongo()
    db = await get_database()
    
    # Connect to NATS
    await nats_client.connect()
    
    while True:
        try:

            running_servers = []
            async for server_doc in db.servers.find({"status": "running"}):
                if server_doc.get("container_id"):
                    running_servers.append(server_doc)
            
            if running_servers:
                logger.info(f"Sampling usage for {len(running_servers)} running servers")

                tasks = []
                for server in running_servers:
                    task = sample_server_usage(
                        server["id"],
                        server["container_id"],
                        db
                    )
                    tasks.append(task)
                
                await asyncio.gather(*tasks, return_exceptions=True)
            else:
                logger.info("No running servers to sample")
            
            # Wait for next sampling interval
            await asyncio.sleep(settings.usage_sampling_interval)
            
        except Exception as e:
            logger.error(f"Error in usage sampling loop: {e}")
            await asyncio.sleep(settings.usage_sampling_interval)


if __name__ == "__main__":
    asyncio.run(usage_sampling_loop())
