from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import socketio
import asyncio

# Local imports from this new structure
from shared import logger, sio
from config import settings
from database.database import init_db
from routers.auth import router as auth_router
from routers.rooms import router as rooms_router
from routers.friends import router as friends_router
from helpers import check_heartbeats # check_heartbeats is now in helpers.py
# Importing sio_events registers the SIO event handlers with the sio object from shared.py
import sio_events 

@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    logger.info("Initializing database...")
    await init_db()
    logger.info("Database initialized")
    
    heartbeat_task = asyncio.create_task(check_heartbeats())
    logger.info("Started heartbeat monitor task")
    
    yield
    
    logger.info("Shutting down application...")
    heartbeat_task.cancel()
    try:
        await heartbeat_task
    except asyncio.CancelledError:
        logger.info("Heartbeat monitor task cancelled")

# Create FastAPI app
app = FastAPI(
    title="MyApp API",
    description="FastAPI backend with PostgreSQL and SQLAlchemy async",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the routers
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(rooms_router, prefix="/rooms", tags=["Rooms"])
app.include_router(friends_router, prefix="/friends", tags=["Friends"])

# Create socketio app, using the sio instance imported from shared.py
socket_app = socketio.ASGIApp(sio, app) 