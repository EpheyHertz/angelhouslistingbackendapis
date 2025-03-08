from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.database import get_db
from app.models import Booking, User
from app.services.email import send_booking_email_to_owner, send_booking_email_to_booker
import logging

router = APIRouter(prefix="/workflows", tags=["Email Workflows"])

# Database session generator
def get_db_session():
    db = get_db()
    try:
        yield db
    finally:
        db.close()

@router.post("/send-reminders/{booking_id}")
async def send_reminders(booking_id: int, db: Session = Depends(get_db_session)):
    """
    Send email reminders to the booking owner and house owner.
    Reminders are sent at intervals of 1, 3, 5, and 7 days before the booking start date.
    """
    try:
        # Fetch booking details
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking or booking.status != "approved":
            raise HTTPException(status_code=404, detail="Booking not found or not approved")

        # Fetch user details
        booking_owner = db.query(User).filter(User.id == booking.user_id).first()
        house_owner = db.query(User).filter(User.id == booking.house.owner_id).first()

        # Schedule reminders
        reminders = [7, 5, 3, 1]
        start_date = booking.start_date
        today = datetime.now().date()

        for days in reminders:
            reminder_date = start_date - timedelta(days=days)
            if reminder_date.date() > today:
                # Send emails
                await send_booking_email_to_booker(
                    booking_owner.email,
                    f"Reminder: Your booking starts in {days} days",
                    booking_id
                )
                await send_booking_email_to_owner(
                    house_owner.email,
                    f"Reminder: A booking starts in {days} days",
                    booking_id
                )

        return {"status": "reminders_sent"}

    except Exception as e:
        logging.error(f"Error sending reminders: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to send reminders")
