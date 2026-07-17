from fastapi import APIRouter

from services.api.routes import assessment, audio, auth, graph, health, learning, rag, search

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(search.router, tags=["search"])
api_router.include_router(rag.router, tags=["rag"])
api_router.include_router(graph.router, tags=["graph"])
api_router.include_router(learning.router, tags=["learning"])
api_router.include_router(audio.router, tags=["audio"])
api_router.include_router(assessment.router, tags=["assessment"])
