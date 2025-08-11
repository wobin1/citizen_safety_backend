import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from modules.shared.db import init_db
from modules.shared.seed import seed_data
from modules.auth.router import router as auth_router
from modules.incidents.router import router as incidents_router
from modules.alerts.router import router as alerts_router
from modules.shared.schema import create_tables
from modules.emergency.router import router as emergency_router
from modules.map.router import router as map_router
from modules.notifications.router import router as notifications_router
import os
from dotenv import load_dotenv
from fastapi import HTTPException
from modules.shared import utils
from modules.shared.response import success_response

load_dotenv()

app = FastAPI(title="Citizen Safety API")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router, prefix="/api/auth")
app.include_router(incidents_router, prefix="/api/incidents")
app.include_router(alerts_router, prefix="/api/alerts")
app.include_router(emergency_router, prefix="/api/emergency")
app.include_router(map_router, prefix="/api/map")
app.include_router(notifications_router, prefix="/api/notifications")

@app.on_event("startup")
async def startup_event():
    """Initialize database tables and seed data on startup"""
    await init_db()
    await create_tables()
    await seed_data()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)