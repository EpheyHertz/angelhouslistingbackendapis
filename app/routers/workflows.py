from datetime import datetime, timedelta
from fastapi import APIRouter, FastAPI, Depends
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db, SessionLocal
from app.models import Booking, BookingStatus
from app.services.email import (
    send_booking_completion_email, 
    send_booking_email_to_owner, 
    send_booking_email_to_booker, 
    send_booking_expiration_email
)
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
    "total_emails_sent": 0,
    "past_bookings_last_run": None,
    "past_bookings_processed": 0,
    "past_bookings_completed": 0,
    "past_bookings_expired": 0
}

# Create the router with unique operation IDs
router = APIRouter(
    prefix="/workflows",
    tags=["Automatic Workflows"],
    responses={404: {"description": "Not found"}}
)

# Set up scheduler
scheduler = AsyncIOScheduler()

# Define the lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start scheduler on app startup
    scheduler.start()
    logger.info("Scheduler started at: %s", datetime.now())
    
    # Add job for booking reminders (runs daily at 9:00 AM)
    reminder_job = scheduler.add_job(
        check_upcoming_bookings,
        CronTrigger(hour=9, minute=0),
        id="booking_reminder_daily",
        replace_existing=True
    )
    
    # Add job for processing past bookings (runs daily at 3:00 AM)
    past_bookings_job = scheduler.add_job(
        process_past_bookings_job,
        CronTrigger(hour=3, minute=0),
        id="past_bookings_processing",
        replace_existing=True
    )
    
    logger.info("Booking reminder job scheduled. Next run: %s", reminder_job.next_run_time)
    logger.info("Past bookings job scheduled. Next run: %s", past_bookings_job.next_run_time)
    
    yield
    
    # Cleanup on shutdown
    scheduler.shutdown()
    logger.info("Scheduler stopped at: %s", datetime.now())

async def process_past_bookings_job():
    """Wrapper job for processing past bookings"""
    start_time = datetime.now()
    EXECUTION_STATS["past_bookings_last_run"] = start_time
    
    try:
        db = SessionLocal()
        try:
            result = await process_past_bookings(db)
            EXECUTION_STATS["past_bookings_processed"] += result["processed"]
            EXECUTION_STATS["past_bookings_completed"] += result["completed"]
            EXECUTION_STATS["past_bookings_expired"] += result["expired"]
            
            logger.info(
                "Processed past bookings in %s seconds: %s completed, %s expired",
                (datetime.now() - start_time).total_seconds(),
                result["completed"],
                result["expired"]
            )
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error in past bookings processing job: {str(e)}", exc_info=True)

async def process_past_bookings(db: AsyncSession):
    """Main function to process past bookings"""
    now = datetime.now()
    cutoff_time = now - timedelta(hours=24)  # Process bookings that ended at least 24 hours ago
    
    # Get all bookings that have ended but haven't been marked completed/expired
    result =db.execute(
        select(Booking).where(
            and_(
                Booking.end_date < cutoff_time,
                Booking.status.in_([BookingStatus.APPROVED, BookingStatus.PENDING])
            )
        )
    )
    bookings = result.scalars().all()
    
    if not bookings:
        logger.info("No past bookings found needing processing")
        return {"processed": 0, "completed": 0, "expired": 0}
    
    completed_count = 0
    expired_count = 0
    
    for booking in bookings:
        if booking.status == BookingStatus.APPROVED:
            # Mark approved bookings as completed
            db.execute(
                update(Booking)
                .where(Booking.id == booking.id)
                .values(status=BookingStatus.COMPLETED)
            )
            completed_count += 1
            logger.info(f"Marked booking {booking.id} as COMPLETED")
            
            # Send completion notification
            send_booking_completion_email(booking)
            
        elif booking.status == BookingStatus.PENDING:
            # Mark pending bookings as expired
            db.execute(
                update(Booking)
                .where(Booking.id == booking.id)
                .values(status=BookingStatus.EXPIRED)
            )
            expired_count += 1
            logger.info(f"Marked booking {booking.id} as EXPIRED")
            
            # Send expiration notification
            send_booking_expiration_email(booking)
    
    await db.commit()
    
    stats = {
        "processed": len(bookings),
        "completed": completed_count,
        "expired": expired_count,
        "timestamp": now.isoformat()
    }
    
    logger.info(f"Processed {len(bookings)} past bookings: {stats}")
    return stats

async def check_upcoming_bookings():
    """Main task to check for upcoming bookings and send reminders"""
    start_time = datetime.now()
    EXECUTION_STATS["last_run"] = start_time
    EXECUTION_STATS["total_runs"] += 1
    
    logger.info("Starting booking reminders check #%s at: %s", 
                EXECUTION_STATS["total_runs"], start_time)
    
    try:
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

# Create a function to set up the scheduler with an app
def setup_scheduler(app: FastAPI):
    # Attach the lifespan to the app
    app.lifespan = lifespan
    
    # Include the router in the app
    app.include_router(router)
    
    logger.info("Scheduler setup completed for the application")
    return app

@router.get(
    "/scheduler-status",
    operation_id="get_scheduler_status",
    summary="Get scheduler status",
    description="Returns current scheduler status and execution statistics"
)
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

@router.post(
    "/trigger-reminders",
    operation_id="trigger_booking_reminders",
    summary="Trigger booking reminders",
    description="Manually triggers the booking reminder job"
)
async def trigger_reminders():
    """Manually trigger the booking reminder job"""
    try:
        await check_upcoming_bookings()
        return {"status": "success", "message": "Booking reminders check completed"}
    except Exception as e:
        logger.error(f"Error in manual reminder trigger: {str(e)}", exc_info=True)
        return {"status": "error", "message": str(e)}

@router.post(
    "/process-past-bookings",
    operation_id="process_past_bookings",
    summary="Process past bookings",
    description="Manually triggers processing of completed/expired bookings"
)
async def trigger_past_bookings_processing(db: AsyncSession = Depends(get_db)):
    """Endpoint to manually trigger past bookings processing"""
    try:
        result = await process_past_bookings(db)
        return {"status": "success", "data": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}