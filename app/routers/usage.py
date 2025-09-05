from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from datetime import datetime, timedelta
from app.models import UsageSample, ErrorResponse
from app.auth import get_current_user, UserInDB
from app.database import get_database

router = APIRouter(tags=["Usage"])


@router.get("/{server_id}/usage")
async def get_server_usage(
    server_id: str,
    from_date: Optional[datetime] = Query(None, alias="from"),
    to_date: Optional[datetime] = Query(None, alias="to"),
    interval: str = Query("1h", description="Aggregation interval: 1m, 5m, 1h, 1d"),
    current_user: UserInDB = Depends(get_current_user),
    db=Depends(get_database)
):
    """Get usage data for a server"""
    # Verify server belongs to user
    server = await db.servers.find_one({
        "id": server_id,
        "user_id": current_user.id
    })
    
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found"
        )
    
    if not to_date:
        to_date = datetime.utcnow()
    if not from_date:
        from_date = to_date - timedelta(days=7)  # Default to last 7 days

    valid_intervals = ["1m", "5m", "1h", "1d"]
    if interval not in valid_intervals:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid interval. Must be one of: {valid_intervals}"
        )
    
    try:

        pipeline = [
            {
                "$match": {
                    "server_id": server_id,
                    "ts": {
                        "$gte": from_date,
                        "$lte": to_date
                    }
                }
            },
            {
                "$sort": {"ts": 1}
            }
        ]
        
        if interval == "1m":
            pass
        elif interval == "5m":
            pipeline.extend([
                {
                    "$group": {
                        "_id": {
                            "$dateTrunc": {
                                "date": "$ts",
                                "unit": "minute",
                                "binSize": 5
                            }
                        },
                        "cpu_pct": {"$avg": "$cpu_pct"},
                        "ram_mib": {"$avg": "$ram_mib"},
                        "disk_gib": {"$avg": "$disk_gib"},
                        "count": {"$sum": 1}
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "ts": "$_id",
                        "cpu_pct": {"$round": ["$cpu_pct", 2]},
                        "ram_mib": {"$round": ["$ram_mib", 2]},
                        "disk_gib": {"$round": ["$disk_gib", 2]},
                        "sample_count": "$count"
                    }
                }
            ])
        elif interval == "1h":
            pipeline.extend([
                {
                    "$group": {
                        "_id": {
                            "$dateTrunc": {
                                "date": "$ts",
                                "unit": "hour"
                            }
                        },
                        "cpu_pct": {"$avg": "$cpu_pct"},
                        "ram_mib": {"$avg": "$ram_mib"},
                        "disk_gib": {"$avg": "$disk_gib"},
                        "count": {"$sum": 1}
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "ts": "$_id",
                        "cpu_pct": {"$round": ["$cpu_pct", 2]},
                        "ram_mib": {"$round": ["$ram_mib", 2]},
                        "disk_gib": {"$round": ["$disk_gib", 2]},
                        "sample_count": "$count"
                    }
                }
            ])
        elif interval == "1d":
            pipeline.extend([
                {
                    "$group": {
                        "_id": {
                            "$dateTrunc": {
                                "date": "$ts",
                                "unit": "day"
                            }
                        },
                        "cpu_pct": {"$avg": "$cpu_pct"},
                        "ram_mib": {"$avg": "$ram_mib"},
                        "disk_gib": {"$avg": "$disk_gib"},
                        "count": {"$sum": 1}
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "ts": "$_id",
                        "cpu_pct": {"$round": ["$cpu_pct", 2]},
                        "ram_mib": {"$round": ["$ram_mib", 2]},
                        "disk_gib": {"$round": ["$disk_gib", 2]},
                        "sample_count": "$count"
                    }
                }
            ])
        
        usage_data = []
        async for doc in db.usage_samples.aggregate(pipeline):
            doc = dict(doc)
            if "ts" in doc and isinstance(doc["ts"], datetime):
                doc["ts"] = doc["ts"].isoformat()
 
            if "_id" in doc:
                doc.pop("_id")
            usage_data.append(doc)
        
        return {
            "server_id": server_id,
            "from_date": from_date,
            "to_date": to_date,
            "interval": interval,
            "data": usage_data
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve usage data: {str(e)}"
        )
