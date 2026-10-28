from fastapi import APIRouter

from app.api.v1 import cognitive, knowledge, memory, planning, reasoning, world

v1_router = APIRouter(prefix="/api/v1")

v1_router.include_router(cognitive.router)
v1_router.include_router(memory.router)
v1_router.include_router(reasoning.router)
v1_router.include_router(planning.router)
v1_router.include_router(world.router)
v1_router.include_router(knowledge.router)
