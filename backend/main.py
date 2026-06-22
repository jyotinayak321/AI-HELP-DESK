"""
AI Help Desk — FastAPI Application Entry Point
================================================
Person 2 owns this file.
Initializes the app, configures CORS, and mounts all routers.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import routers (Person 1's admin + Person 2's tickets)
from routers.admin import router as admin_router
from routers.tickets import router as tickets_router


# =====================================================================
# APP INITIALIZATION
# =====================================================================

app = FastAPI(
    title="AI Help Desk",
    description="Complaint Classification & Logging Application — Phase 1",
    version="1.0.0",
    docs_url="/docs",       # Swagger UI at /docs
    redoc_url="/redoc",     # ReDoc at /redoc
)


# =====================================================================
# CORS MIDDLEWARE (Allow frontend to connect during development)
# =====================================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],         # Lock down in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =====================================================================
# MOUNT ROUTERS
# =====================================================================

app.include_router(admin_router, prefix="/api/admin", tags=["Admin & Registry"])
app.include_router(tickets_router, prefix="/api", tags=["Intake & Tickets"])


# =====================================================================
# HEALTH CHECK
# =====================================================================

@app.get("/", tags=["Health"])
def health_check():
    """Simple health check endpoint to confirm the server is running."""
    return {
        "status": "ok",
        "service": "AI Help Desk API",
        "version": "1.0.0",
    }
