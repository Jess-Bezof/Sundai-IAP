from fastapi import FastAPI, Depends, HTTPException, Security, status, BackgroundTasks
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session
import database
from database import engine, get_db
import logging
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_KEY = os.getenv("API_KEY")
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def get_api_key(api_key_header: str = Security(api_key_header)):
    if not API_KEY:
        # If API_KEY is not set on server, fail safe (or log warning)
        # For security, we should reject if no key is configured to prevent open access by mistake
        logger.error("API_KEY environment variable is not set!")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server misconfiguration: API Key not set"
        )
        
    if api_key_header == API_KEY:
        return api_key_header
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Could not validate credentials"
    )

# Initialize database tables
database.Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    logging.info("Starting up Sundai IAP API...")
    if not API_KEY:
        logger.warning("WARNING: API_KEY is not set in environment variables!")
    yield
    # Shutdown logic
    logging.info("Shutting down Sundai IAP API...")

app = FastAPI(title="Sundai IAP 2026 Automation API", lifespan=lifespan)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Service is running"}

@app.post("/run-automation", dependencies=[Depends(get_api_key)])
def trigger_automation(background_tasks: BackgroundTasks):
    """
    Trigger the daily automation script in the background.
    """
    try:
        # Import inside the function to avoid circular imports
        from main import run_daily_automation
        
        background_tasks.add_task(run_daily_automation)
        
        return {"status": "success", "message": "Automation started in background"}
    except Exception as e:
        logger.error(f"Failed to start automation: {e}")
        raise HTTPException(status_code=500, detail=str(e))
