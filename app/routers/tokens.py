from ..services.oauth import decode_token, create_access_token, create_refresh_token
from datetime import timedelta
from fastapi import Depends, HTTPException, status, APIRouter
from sqlalchemy.orm import Session
from app import models
from app.database import get_db
from app.config import SECRET_KEY
from jose import JWTError
import pytz  # Ensure pytz is installed and imported

# OAuth2 configuration
# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="users/login")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 960

# Router setup
router = APIRouter(prefix="/tokens", tags=["Token"])

@router.post("/refresh")
async def refresh_token(refresh_request: dict, db: Session = Depends(get_db)):
    """
    Generates a new access and refresh token using the refresh token.
    Invalidates the old refresh token.
    """
    token = refresh_request.get("refresh_token")
    if not token:
        raise HTTPException(status_code=400, detail="Refresh token is required")

    try:
        # Decode the token and get the user information
        decoded = decode_token(token)
        # print(decoded)

        # Invalidate the old refresh token
        # You could delete the old token or mark it as invalid in the database
        db_refresh_token = db.query(models.RefreshToken).filter(models.RefreshToken.token == token).first()
        if db_refresh_token:
            db.delete(db_refresh_token)
            db.commit()

        # Generate new access and refresh tokens
        access_token = create_access_token(
            data={"username": decoded["username"], "user_id": decoded["user_id"]},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        )
        refresh_token = create_refresh_token(
            data={"username": decoded["username"], "user_id": decoded["user_id"]},
            expires_delta=timedelta(days=14),
        )

        # Store the new refresh token in the database
        new_db_refresh_token = models.RefreshToken(token=refresh_token, user_id=decoded["user_id"])
        db.add(new_db_refresh_token)
        db.commit()

        return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
