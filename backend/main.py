from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.admin import router as admin_router
from routers.tickets import router as tickets_router

app = FastAPI(
    title="AI Help Desk",
    description="Complaint Classification Phase 1",
    version="1.0.0",
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

@app.get("/", tags=["Health"])
def health_check():
    return {"status": "ok", "version": "1.0.0"}
