from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from app.models import (
    Server, ServerCreate, ServerUpdate, ServerInDB, ServerStatus,
    ErrorResponse, SuccessResponse
)
from app.auth import get_current_user, UserInDB
from app.database import get_database
from app.docker_manager import docker_manager
from app.nats_client import publish_server_created, publish_server_started, publish_server_stopped
from datetime import datetime
import uuid

router = APIRouter(tags=["Servers"])


@router.post("", response_model=Server)
async def create_server(
    server_data: ServerCreate,
    current_user: UserInDB = Depends(get_current_user),
    db=Depends(get_database)
):
    """Create a new server"""

    if server_data.cpu_limit <= 0 or server_data.cores <= 0 or server_data.ram_gib <= 0 or server_data.disk_gib <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="All resource values must be positive"
        )
    
    server = ServerInDB(
        user_id=current_user.id,
        name=server_data.name,
        image=server_data.image,
        cpu_limit=server_data.cpu_limit,
        cores=server_data.cores,
        ram_gib=server_data.ram_gib,
        disk_gib=server_data.disk_gib,
        status=ServerStatus.CREATED
    )
    
    try:
        # Create Docker container
        container_id = await docker_manager.create_container(server)
        server.container_id = container_id
        
  
        await db.servers.insert_one(server.dict())
        
        # Publish event in NATS
        await publish_server_created(server.id)
        
        return Server(
            id=server.id,
            user_id=server.user_id,
            name=server.name,
            image=server.image,
            cpu_limit=server.cpu_limit,
            cores=server.cores,
            ram_gib=server.ram_gib,
            disk_gib=server.disk_gib,
            status=server.status,
            container_id=server.container_id,
            created_at=server.created_at,
            updated_at=server.updated_at
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create server: {str(e)}"
        )


@router.get("", response_model=List[Server])
async def list_servers(
    current_user: UserInDB = Depends(get_current_user),
    db=Depends(get_database)
):
    """List all servers for the current user"""
    servers = []
    async for server_doc in db.servers.find({"user_id": current_user.id}):
        servers.append(Server(**server_doc))
    
    return servers


@router.get("/{server_id}", response_model=Server)
async def get_server(
    server_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db=Depends(get_database)
):
    """Get a specific server"""
    server_doc = await db.servers.find_one({
        "id": server_id,
        "user_id": current_user.id
    })
    
    if not server_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )
    
    return Server(**server_doc)


@router.post("/{server_id}/start", response_model=SuccessResponse)
async def start_server(
    server_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db=Depends(get_database)
):
    """Start a server"""
    server_doc = await db.servers.find_one({
        "id": server_id,
        "user_id": current_user.id
    })
    
    if not server_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )
    
    server = ServerInDB(**server_doc)
    
    if server.status == ServerStatus.RUNNING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Server is already running"
        )
    
    if not server.container_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Server container not found"
        )
    
    try:
        success = await docker_manager.start_container(server.container_id)
        if success:
            await db.servers.update_one(
                {"id": server_id},
                {
                    "$set": {
                        "status": ServerStatus.RUNNING,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            # Publish event in NATS
            await publish_server_started(server_id)
            
            return SuccessResponse(message="Server started successfully")
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to start server"
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start server: {str(e)}"
        )


@router.post("/{server_id}/stop", response_model=SuccessResponse)
async def stop_server(
    server_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db=Depends(get_database)
):
    """Stop a server"""
    server_doc = await db.servers.find_one({
        "id": server_id,
        "user_id": current_user.id
    })
    
    if not server_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )
    
    server = ServerInDB(**server_doc)
    
    if server.status == ServerStatus.STOPPED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Server is already stopped"
        )
    
    if not server.container_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Server container not found"
        )
    
    try:
        success = await docker_manager.stop_container(server.container_id)
        if success:
            await db.servers.update_one(
                {"id": server_id},
                {
                    "$set": {
                        "status": ServerStatus.STOPPED,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            # Publish event in NATS
            await publish_server_stopped(server_id)
            
            return SuccessResponse(message="Server stopped successfully")
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to stop server"
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop server: {str(e)}"
        )


@router.patch("/{server_id}", response_model=Server)
async def update_server(
    server_id: str,
    server_update: ServerUpdate,
    current_user: UserInDB = Depends(get_current_user),
    db=Depends(get_database)
):
    """Update server resources"""
    server_doc = await db.servers.find_one({
        "id": server_id,
        "user_id": current_user.id
    })
    
    if not server_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )
    
    server = ServerInDB(**server_doc)
    
    update_data = server_update.dict(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )
    
    for field in ["cpu_limit", "cores", "ram_gib", "disk_gib"]:
        if field in update_data and update_data[field] <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field} must be positive"
            )
    
    for field, value in update_data.items():
        setattr(server, field, value)
    
    server.updated_at = datetime.utcnow()
    
    try:
        # If server is running and resources changed, restart it
        if server.status == ServerStatus.RUNNING and server.container_id:
            
            resource_fields = ["cpu_limit", "cores", "ram_gib", "disk_gib"]
            if any(field in update_data for field in resource_fields):
                
                success = await docker_manager.update_container_resources(
                    server.container_id, server
                )
                if not success:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to update server resources"
                    )
        

        await db.servers.update_one(
            {"id": server_id},
            {"$set": server.dict()}
        )
        
        return Server(
            id=server.id,
            user_id=server.user_id,
            name=server.name,
            image=server.image,
            cpu_limit=server.cpu_limit,
            cores=server.cores,
            ram_gib=server.ram_gib,
            disk_gib=server.disk_gib,
            status=server.status,
            container_id=server.container_id,
            created_at=server.created_at,
            updated_at=server.updated_at
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update server: {str(e)}"
        )


@router.delete("/{server_id}", response_model=SuccessResponse)
async def delete_server(
    server_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db=Depends(get_database)
):
    """Delete a server"""
    server_doc = await db.servers.find_one({
        "id": server_id,
        "user_id": current_user.id
    })
    
    if not server_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )
    
    server = ServerInDB(**server_doc)
    
    try:
        # Delete Docker container if it exists
        if server.container_id:
            await docker_manager.delete_container(server.container_id)
        

        await db.servers.delete_one({"id": server_id, "user_id": current_user.id})
        
        return SuccessResponse(message="Server deleted successfully")
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete server: {str(e)}"
        )
