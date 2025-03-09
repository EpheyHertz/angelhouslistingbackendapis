from datetime import datetime, timedelta
from fastapi import APIRouter, FastAPI, Depends
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db, SessionLocal
from app.models import Booking
from app.services.email import send_booking_email_to_owner, send_booking_email_to_booker
from contextlib import asynccontextmanager
import logging
from typing import List
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.config import DATABASE_URL  
from apscheduler.triggers.cron import CronTrigger

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Define target days for reminders
REMINDER_DAYS = [1, 3, 5, 7]

# Global variable to track executions
EXECUTION_STATS = {
    "last_run": None,
    "total_runs": 0,
    "total_bookings_processed": 0,
    "total_emails_sent": 0
}

# Create the router
router = APIRouter(prefix="/workflows", tags=["Automatic Workflows"])

# Set up scheduler
scheduler = AsyncIOScheduler()

# Define the lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start scheduler on app startup
    scheduler.start()
    logger.info("Scheduler started at: %s", datetime.now())
    print("Scheduler started at: ", datetime.now())
    # Add job for booking reminders
    job = scheduler.add_job(
        check_upcoming_bookings,
        CronTrigger(hour=9,minute=0),  # Run at 9:00 AM every day
        id="booking_reminder_daily",
        replace_existing=True
    )
    
    # Log job information
    next_run = job.next_run_time
    logger.info("Booking reminder job scheduled. Next run: %s", next_run)
    
    yield
    
    # Cleanup on shutdown
    scheduler.shutdown()
    logger.info("Scheduler stopped at: %s", datetime.now())

# Create a function to set up the scheduler with an app
def setup_scheduler(app: FastAPI):
    # Attach the lifespan to the app
    app.lifespan = lifespan
    
    # Include the router in the app
    app.include_router(router)
    
    logger.info("Scheduler setup completed for the application")
    return app

@router.get("/scheduler-status")
async def scheduler_status():
    """Endpoint to check scheduler status and next run times"""
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            "function": job.func.__name__,
            "trigger": str(job.trigger)
        })
    
    return {
        "scheduler_running": scheduler.running,
        "jobs": jobs,
        "current_time": datetime.now().isoformat(),
        "execution_stats": EXECUTION_STATS
    }

async def check_upcoming_bookings():
    """Main task to check for upcoming bookings and send reminders"""
    start_time = datetime.now()
    EXECUTION_STATS["last_run"] = start_time
    EXECUTION_STATS["total_runs"] += 1
    
    logger.info("Starting booking reminders check #%s at: %s", 
                EXECUTION_STATS["total_runs"], start_time)
    
    try:
        # Create a new session for this task
        db = SessionLocal()
        try:
            # Get bookings that need reminders
            bookings = get_bookings_for_reminders_sync(db)
            
            if not bookings:
                logger.info("No bookings found needing reminders (run #%s)", 
                           EXECUTION_STATS["total_runs"])
                return
                
            EXECUTION_STATS["total_bookings_processed"] += len(bookings)
            logger.info(f"Found {len(bookings)} bookings needing reminders")
            
            # Send reminders for each booking
            today = datetime.now().date()
            emails_sent = 0
            for booking in bookings:
                days_remaining = (booking.start_date.date() - today).days
                sent = await send_reminder_emails(booking, days_remaining)
                if sent:
                    emails_sent += 2  # 2 emails per booking (guest + owner)
            
            EXECUTION_STATS["total_emails_sent"] += emails_sent
            
            logger.info("Completed sending %s reminder emails in %s seconds (run #%s)", 
                      emails_sent,
                      (datetime.now() - start_time).total_seconds(),
                      EXECUTION_STATS["total_runs"])
                
        finally:
            db.close()
                
    except Exception as e:
        logger.error(f"Error in booking reminder task (run #{EXECUTION_STATS['total_runs']}): {str(e)}", 
                    exc_info=True)

def get_bookings_for_reminders_sync(db) -> List[Booking]:
    """Get all bookings that need reminders today (synchronous version)"""
    today = datetime.now().date()
    
    # Calculate target dates for reminders
    target_dates = [today + timedelta(days=days) for days in REMINDER_DAYS]
    logger.info("Checking for bookings on dates: %s", target_dates)
    
    try:
        # Fetch confirmed bookings starting on target dates
        bookings = db.query(Booking).filter(
            Booking.start_date.in_(target_dates),
            Booking.status == "approved"
        ).all()
        
        # Log results
        if bookings:
            booking_details = [f"ID: {b.id}, Date: {b.start_date}" for b in bookings]
            logger.info("Found bookings: %s", booking_details)
        
        return bookings
        
    except Exception as e:
        logger.error(f"Database error fetching bookings: {str(e)}", exc_info=True)
        return []

async def send_reminder_emails(booking: Booking, days_remaining: int):
    """Send reminders for a specific booking"""
    try:
        # Validate booking data
        if not booking.house or not booking.user:
            logger.warning(f"Booking {booking.id} has missing property or guest data")
            return False
            
        if not hasattr(booking.house, 'owner') or not booking.house.owner:
            logger.warning(f"Property for booking {booking.id} has missing owner data")
            return False
        
        # Format dates
        start_date = booking.start_date.strftime("%Y-%m-%d %H:%M:%S")
        end_date = booking.end_date.strftime("%Y-%m-%d %H:%M:%S")
        
        # Common email parameters
        email_params = {
            "house_title": booking.house.title,
            "house_owner_name": booking.house.owner.full_name or booking.house.owner.username,
            "booking_owner_username": booking.user.username or booking.user.full_name,
            "start_date": start_date,
            "end_date": end_date,
            "booking_id": str(booking.id),
            "days_remaining": days_remaining
        }
        
        # Send to booker
        send_booking_email_to_booker(
            to_email=booking.user.email,
            subject=f"Reminder: Your booking starts in {days_remaining} days",
            template_name="workflow_user.html",
            **email_params
        )
        
        # Send to owner
        send_booking_email_to_owner(
            to_email=booking.house.owner.email,
            subject=f"Reminder: Booking starts in {days_remaining} days",
            template_name="workflow_owner.html",
            **email_params
        )
        
        logger.info(f"Sent reminders for booking {booking.id} ({days_remaining} days remaining)")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send reminders for booking {booking.id}: {str(e)}", exc_info=True)
        return False
    
async def call_trigger_reminders():
    """Manually trigger the booking reminder job"""
    try:
        await check_upcoming_bookings()
        return {"status": "success", "message": "Booking reminders check completed"}
    except Exception as e:
        logger.error(f"Error in manual reminder trigger: {str(e)}", exc_info=True)
        return {"status": "error", "message": str(e)}



@router.post("/trigger-reminders")
async def trigger_reminders():
    """Manually trigger the booking reminder job"""
    try:
        await check_upcoming_bookings()
        return {"status": "success", "message": "Booking reminders check completed"}
    except Exception as e:
        logger.error(f"Error in manual reminder trigger: {str(e)}", exc_info=True)
        return {"status": "error", "message": str(e)}