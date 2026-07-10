from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from routers.admin import router as admin_router
from routers.tickets import router as tickets_router
from routers.voice import router as voice_router
from routers.livekit import router as livekit_router   # Phase 4: LiveKit transport
from security import get_current_user, CurrentUser, require_operator
from config import settings
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn
import os

app = FastAPI(
    title="AI Help Desk",
    description="Complaint Classification Phase 1 + Voice Layer Phase 2 + LiveKit Phase 4",
    version="4.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin_router,   prefix="/api/admin",   tags=["Admin"])
app.include_router(tickets_router, prefix="/api",         tags=["Tickets"])
app.include_router(voice_router,   prefix="/api/voice",   tags=["Voice"])
app.include_router(livekit_router, prefix="/api/livekit", tags=["LiveKit"])  # Phase 4

@app.get("/", tags=["Health"])
def health_check():
    return {"status": "ok", "version": "1.0.0"}

@app.get("/api/me", tags=["Auth"])
def get_me(user: CurrentUser = Depends(get_current_user)):
    """
    Returns the currently logged-in user's service number and role.
    The React frontend calls this after login to know the persona.
    """
    return {
        "service_no": user.service_no,
        "role": user.role,
        "managed_team": user.managed_team,
    }


# Mount Frontend if exists (Airgapped Deployment)
frontend_dist_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))
if os.path.isdir(frontend_dist_path):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist_path, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str):
        # Serve index.html for all other routes to support React Router
        return FileResponse(os.path.join(frontend_dist_path, "index.html"))

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )