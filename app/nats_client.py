import asyncio
import json
from typing import Dict, Any
from nats import connect as nats_connect
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class NATSClient:
    def __init__(self):
        self.nc = None
    
    async def connect(self):
        try:
            self.nc = await nats_connect(settings.nats_url)
            logger.info("Connected to NATS server")
        except Exception as e:
            logger.error(f"Failed to connect to NATS: {e}")
            raise
    
    async def close(self):
       
        if self.nc:
            await self.nc.close()
    
    # Publish an event to NATS
    async def publish_event(self, subject: str, data: Dict[str, Any]):
        
        try:
            if not self.nc:
                await self.connect()
            
            message = json.dumps(data, default=str)
            await self.nc.publish(subject, message.encode())
            logger.info(f"Published event to {subject}: {data}")
        except Exception as e:
            logger.error(f"Failed to publish event to {subject}: {e}")
    
    # Subscribe to events from NATS
    async def subscribe_to_events(self, subject: str, handler):
        
        try:
            if not self.nc:
                await self.connect()
            
            async def message_handler(msg):
                try:
                    data = json.loads(msg.data.decode())
                    await handler(data)
                except Exception as e:
                    logger.error(f"Error handling message from {subject}: {e}")
            
            await self.nc.subscribe(subject, cb=message_handler)
            logger.info(f"Subscribed to {subject}")
        except Exception as e:
            logger.error(f"Failed to subscribe to {subject}: {e}")



nats_client = NATSClient()



async def publish_server_created(server_id: str):
    """Publish server created event"""
    await nats_client.publish_event("server.created", {"server_id": server_id})


async def publish_server_started(server_id: str):
    """Publish server started event"""
    await nats_client.publish_event("server.started", {"server_id": server_id})


async def publish_server_stopped(server_id: str):
    """Publish server stopped event"""
    await nats_client.publish_event("server.stopped", {"server_id": server_id})


async def publish_usage_sampled(server_id: str, ts: str):
    """Publish usage sampled event"""
    await nats_client.publish_event("usage.sampled", {"server_id": server_id, "ts": ts})


async def publish_invoice_generated(invoice_id: str):
    """Publish invoice generated event"""
    await nats_client.publish_event("invoice.generated", {"invoice_id": invoice_id})
