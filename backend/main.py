import logging
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from routers.admin import router as admin_router
from routers.tickets import router as tickets_router
from routers.voice import router as voice_router
from security import get_current_user, CurrentUser, require_operator
from config import settings
import uvicorn

# Without this, every logger.info() call in the app (voice session FSM
# transitions, STT/TTS timing, etc.) is silently dropped — the root
# logger defaults to WARNING with no handler attached.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(
    title="AI Help Desk",
    description="Complaint Classification Phase 1 + Voice Layer Phase 2",
    version="2.0.0",
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

app.include_router(admin_router, prefix="/api/admin", tags=["Admin"])
app.include_router(tickets_router, prefix="/api", tags=["Tickets"])
app.include_router(voice_router, prefix="/api/voice", tags=["Voice"])

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


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )