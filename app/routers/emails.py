from fastapi import APIRouter, Depends, HTTPException, status
from app.models import SuccessResponse, ErrorResponse
from app.auth import get_current_user, UserInDB
from app.database import get_database
from app.workers.email_worker import send_weekly_email
import asyncio

router = APIRouter(tags=["Emails"])


@router.post("/weekly/trigger", response_model=SuccessResponse)
async def trigger_weekly_email(
    current_user: UserInDB = Depends(get_current_user),
    db=Depends(get_database)
):
    """Trigger a weekly email for the current user"""
    try:
        # Send the weekly email asynchronously
        asyncio.create_task(send_weekly_email(current_user.id, db))
        
        return SuccessResponse(message="Weekly email triggered successfully")
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger weekly email: {str(e)}"
        )
