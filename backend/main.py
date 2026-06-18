
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import init_db

app = FastAPI(
    title="AI Help Desk",
    description="UDAAN IAF Air-Gapped System",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    print("Server starting...")

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "system": "AI Help Desk",
        "version": "1.0.0"
    }


