"""项目 CRUD API"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_projects():
    return {"projects": []}


@router.post("/")
async def create_project():
    return {"status": "placeholder"}
