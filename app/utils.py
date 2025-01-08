from passlib.context import CryptContext
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app import models
from app.services.oauth import verify_token

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt
    """
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash
    """
    return pwd_context.verify(plain_password, hashed_password)

def check_house_owner(db: Session, house_id: int, user_id: int) -> models.House:
    """
    Check if a house exists and belongs to the user
    """
    house = db.query(models.House).filter(models.House.id == house_id).first()
    if not house:
        raise HTTPException(status_code=404, detail="House not found")
    
    if house.owner_id != user_id:
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to modify this house"
        )
    
    return house

def log_admin_action(db: Session, user_id: int, action: str):
    """
    Log an admin action
    """
    log = models.Log(user_id=user_id, action=action)
    db.add(log)
    db.commit()
    return log

def verify_password_reset_token(token: str) -> str:
    """
    Verify a password reset token and return the email
    """
    try:
        email = verify_token(token)
        return email
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
