"""backend/routers/styles.py"""
from fastapi import APIRouter
from models.schemas import StylesResponse, TravelStyle
from services.style_service import get_all_styles

router = APIRouter()

@router.get("/styles", response_model=StylesResponse)
async def get_styles():
    return StylesResponse(styles=[TravelStyle(**s) for s in get_all_styles()])
