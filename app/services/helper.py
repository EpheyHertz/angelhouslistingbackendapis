from fastapi import HTTPException, status, Depends, Request
from sqlalchemy.orm import Session
import random
import string
import logging
from datetime import datetime, timedelta
from .. import models, schemas
from . import email
logger = logging.getLogger(__name__)

# Function to generate a verification code
def generate_verification_code():
    return ''.join(random.choices(string.digits, k=6))

# Function to send verification code via email (for mobile platforms)
async def resend_verification_code(user: models.User, platform: str, db: Session):
    verification_code = generate_verification_code()

    try:
        # Send verification code email to the user
        email.send_verification_code(user.email, verification_code, username=user.username)
        logger.info(f"Resent verification code to: {user.email}")

        # Delete any existing verification code for the user
        db.query(models.VerificationCode).filter(models.VerificationCode.user_id == user.id).delete()
        
        # Set a new verification code with expiration time
        expiration_time = datetime.now() + timedelta(hours=1)
        verification_code_entry = models.VerificationCode(
            code=verification_code,
            user_id=user.id,
            expiration_date=expiration_time
        )
        
        # Add the new verification code entry to the database
        db.add(verification_code_entry)
        db.commit()

        return {"message": "Verification code sent successfully."}
    except Exception as e:
        logger.error(f"Failed to resend verification code to {user.email}: {str(e)}")
        raise HTTPException(status_code=500, detail="Unable to resend verification code")

# Function to send verification link via email (for non-mobile platforms)
async def resend_verification_link(user: models.User, db: Session):
    try:
        # Send verification email with the link
        email.send_verification_email(user.email, username=user.username)
        logger.info(f"Resent verification link to: {user.email}")
        return {"message": "Verification link sent successfully."}
    except Exception as e:
        logger.error(f"Failed to resend verification link to {user.email}: {str(e)}")
        raise HTTPException(status_code=500, detail="Unable to resend verification link")
