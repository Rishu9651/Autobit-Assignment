import docker
import asyncio
import psutil
from typing import Optional, Dict, Any
from app.config import settings
from app.models import ServerInDB, ServerStatus
import logging

logger = logging.getLogger(__name__)


class DockerManager:
    def __init__(self):
        try:
            # Use DOCKER_HOST environment variable if available, otherwise use default
            docker_host = settings.DOCKER_HOST if hasattr(settings, 'DOCKER_HOST') else None
            if docker_host:
                logger.info(f"Connecting to Docker at: {docker_host}")
                self.client = docker.DockerClient(base_url=docker_host)
            else:
                logger.info("No DOCKER_HOST specified, using default Docker connection")
                self.client = docker.from_env()
            
            # Test connection
            logger.info("Testing Docker connection...")
            self.client.ping()
            logger.info("✅ Docker connection successful!")
            self.available = True
        except Exception as e:
            logger.error(f"❌ Docker connection failed: {e}")
            logger.warning("Running in mock mode. Containers will not be created.")
            self.client = None
            self.available = False
    
    def get_status(self) -> Dict[str, Any]:
        """Get Docker manager status"""
        if not self.available or self.client is None:
            return {
                "available": False,
                "error": "Docker not available",
                "mode": "mock"
            }
        
        try:
            info = self.client.info()
            return {
                "available": True,
                "mode": "real",
                "docker_version": info.get("ServerVersion", "unknown"),
                "containers_running": info.get("ContainersRunning", 0),
                "containers_total": info.get("Containers", 0),
                "images": info.get("Images", 0)
            }
        except Exception as e:
            return {
                "available": False,
                "error": str(e),
                "mode": "error"
            }


    async def create_container(self, server: ServerInDB) -> str:
        """Create a Docker container for a server"""
        if not self.available or self.client is None:
            logger.warning(
                f"Docker not available, returning mock container ID for server {server.id}"
            )
            return f"mock-container-{server.id}"
        
        try:
            # Calculate CPU quota and period
            cpu_quota = int(server.cpu_limit * 100000)
            cpu_period = 100000

            # Memory limit in bytes
            memory_limit = int(server.ram_gib * 1024 * 1024 * 1024)

            image_name = server.image.lower()

            # ✅ Ensure image exists locally, pull if missing
            try:
                self.client.images.get(image_name)
                logger.info(f"Image {image_name} found locally")
            except Exception:
                logger.info(f"Image {image_name} not found, pulling...")
                self.client.images.pull(*image_name.split(":", 1))

            # Create container
            container = self.client.containers.create(
                image=image_name,
                name=f"autobit-server-{server.id}",
                cpu_quota=cpu_quota,
                cpu_period=cpu_period,
                mem_limit=memory_limit,
                memswap_limit=memory_limit,  # Disable swap
                detach=True,
                # Disk size enforcement not supported -> only tracked in DB
            )

            return container.id

        except Exception as e:
            logger.error(f"Failed to create container for server {server.id}: {e}")
            raise


    
    async def start_container(self, container_id: str) -> bool:
        """Start a Docker container"""
        if not self.available or self.client is None:
            logger.warning(f"Docker not available, mock starting container {container_id}")
            return True
        
        try:
            container = self.client.containers.get(container_id)
            container.start()
            return True
        except Exception as e:
            logger.error(f"Failed to start container {container_id}: {e}")
            return False
    
    async def stop_container(self, container_id: str) -> bool:
        """Stop a Docker container"""
        if not self.available or self.client is None:
            logger.warning(f"Docker not available, mock stopping container {container_id}")
            return True
        
        try:
            container = self.client.containers.get(container_id)
            container.stop(timeout=10)
            return True
        except Exception as e:
            logger.error(f"Failed to stop container {container_id}: {e}")
            return False
    
    async def delete_container(self, container_id: str) -> bool:
        """Delete a Docker container"""
        if not self.available or self.client is None:
            logger.warning(f"Docker not available, mock deleting container {container_id}")
            return True
        
        try:
            container = self.client.containers.get(container_id)
            container.remove(force=True)
            return True
        except Exception as e:
            logger.error(f"Failed to delete container {container_id}: {e}")
            return False
    
    async def get_container_stats(self, container_id: str) -> Optional[Dict[str, Any]]:
        """Get container resource usage statistics"""
        if not self.available or self.client is None:
            logger.warning(f"Docker not available, returning mock stats for container {container_id}")
            return {
                'cpu_percent': 25.0,  # Mock CPU usage
                'memory_usage_mb': 512.0,  # Mock memory usage
                'disk_usage_gb': 1.0  # Mock disk usage
            }
        
        try:
            container = self.client.containers.get(container_id)
            stats = container.stats(stream=False)
            
            # Calculate CPU percentage
            cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - stats['precpu_stats']['cpu_usage']['total_usage']
            system_delta = stats['cpu_stats']['system_cpu_usage'] - stats['precpu_stats']['system_cpu_usage']
            cpu_percent = 0.0
            
            if system_delta > 0 and cpu_delta > 0:
                cpu_percent = (cpu_delta / system_delta) * len(stats['cpu_stats']['cpu_usage']['percpu_usage']) * 100.0
            
            # memory usage in MB
            memory_usage = stats['memory_stats']['usage'] / (1024 * 1024)
        
            disk_usage = 0.0
            if 'storage_stats' in stats:
                disk_usage = stats['storage_stats'].get('size', 0) / (1024 * 1024 * 1024)  # Convert to GB
            
            return {
                'cpu_percent': round(cpu_percent, 2),
                'memory_mb': round(memory_usage, 2),
                'disk_gb': round(disk_usage, 2)
            }
            
        except Exception as e:
            logger.error(f"Failed to get stats for container {container_id}: {e}")
            return None
    
    async def update_container_resources(self, container_id: str, server: ServerInDB) -> bool:
        """Update container resource limits (requires container restart)"""
        try:
       
            await self.stop_container(container_id)
            
            await self.delete_container(container_id)

            new_container_id = await self.create_container(server)
            
            await self.start_container(new_container_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update resources for container {container_id}: {e}")
            return False
    
    async def is_container_running(self, container_id: str) -> bool:
        """Check if a container is running"""
        try:
            container = self.client.containers.get(container_id)
            return container.status == 'running'
        except Exception as e:
            logger.error(f"Failed to check container status {container_id}: {e}")
            return False


docker_manager = DockerManager()
