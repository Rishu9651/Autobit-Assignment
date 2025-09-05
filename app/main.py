from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, servers, usage, billing, emails
from app.database import connect_to_mongo, close_mongo_connection
from app.nats_client import nats_client
from app.config import settings
from app.docker_manager import docker_manager
import logging
import time
from fastapi.responses import JSONResponse

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AutoBit Backend System",
    description="Production-ready backend system for Docker container management with metered billing",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust as needed for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    try:
        response = await call_next(request)
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        response = JSONResponse(status_code=500, content={"detail": "Internal Server Error"})
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

# Register all API routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(servers.router, prefix="/servers", tags=["Servers"])
app.include_router(usage.router, prefix="/servers", tags=["Usage"])
app.include_router(billing.router, prefix="/billing", tags=["Billing"])
app.include_router(emails.router, prefix="/emails", tags=["Emails"])


@app.on_event("startup")
async def startup_event():
    """Application startup event"""
    logger.info("Starting AutoBit Backend System...")
    
    try:
        # Connect to MongoDB
        await connect_to_mongo()
        logger.info("Connected to MongoDB")
        
        # Connect to NATS
        await nats_client.connect()
        logger.info("Connected to NATS")
        
        
        logger.info("AutoBit Backend System started successfully!")
        
    except Exception as e:
        logger.error(f"Failed to start system: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event"""
    logger.info("Shutting down AutoBit Backend System...")
    
    try:
        # Close MongoDB connection
        await close_mongo_connection()
        logger.info("MongoDB connection closed")
        
        # Close NATS connection
        await nats_client.close()
        logger.info("NATS connection closed")
        
        logger.info("AutoBit Backend System shutdown complete")
        
    except Exception as e:
        logger.error(f" Error during shutdown: {e}")


@app.get("/health", tags=["Health"])
async def health_check():
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "service": "autobit-backend"
    }


