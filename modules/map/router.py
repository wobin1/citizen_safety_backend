from fastapi import APIRouter, HTTPException
from modules.shared.utils import get_all_locations
from modules.shared.response import success_response

router = APIRouter()

@router.get("/")
async def get_map_locations():
    """
    Endpoint to fetch all map locations (incidents, alerts, emergencies).
    """
    try:
        locations = await get_all_locations()
        return success_response(locations, "Map data fetched successfully")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
