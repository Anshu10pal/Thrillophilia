"""backend/routers/nearby.py"""
from fastapi import APIRouter
from models.schemas import NearbyResponse, NearbyCityItem
from services.nearby_service import get_nearby_cities, get_sub_regions, should_auto_split

router = APIRouter()

@router.get("/nearby/{city}", response_model=NearbyResponse)
async def get_nearby(city: str, style: str = "balanced", days: int = 5):
    dest         = city.lower().strip()
    nearby       = get_nearby_cities(dest, style)
    subs         = get_sub_regions(dest)
    auto         = should_auto_split(dest, days)
    nearby_items = [
        NearbyCityItem(
            name=n.name, distance_km=n.distance_km, drive_hours=n.drive_hours,
            description=n.description, style_match=n.style_match, emoji=n.emoji,
        ) for n in nearby
    ]
    return NearbyResponse(city=city, sub_regions=subs, nearby=nearby_items, auto_split=auto)
