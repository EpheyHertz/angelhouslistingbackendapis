from datetime import datetime, timedelta,timezone
from typing import Optional
from fastapi import Depends, HTTPException, status, APIRouter
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from app import models
from app.database import get_db
from app.config import SECRET_KEY
import pytz  



# OAuth2 configuration
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="users/login")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 960

# Router setup
router = APIRouter(prefix="/tokens", tags=["Token"])
# expires_delta=timedelta(days=14)
def create_access_token(data: dict, expires_delta: Optional[timedelta] =timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES) ):
    """
    Create a JWT access token
    """
    print("Access Data:",data)
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    # to_encode.update({ "sub": data.username})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    print(encoded_jwt)
    return encoded_jwt

def create_refresh_token(data:dict, expires_delta: Optional[timedelta]=timedelta(days=14)):
    """
    Create a JWT refresh token
    """
    # print("Refresh Data:",data)
    to_encode=data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=14)
    
    # utc_now = datetime.now(pytz.UTC)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str):
    """
    Decode a JWT token
    """
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        ) from e



def verify_token(token: str, credentials_exception):
    """
    Verify a JWT token and return the email from payload
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # print(payload)
        email: str = payload.get("username")
        if email is None:
            raise credentials_exception
        return email
    except JWTError:
        raise credentials_exception


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> models.User:
    """
    Get the current authenticated user
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    email = verify_token(token, credentials_exception)
    user = db.query(models.User).filter(models.User.email == email).first()
    
    if user is None:
        raise credentials_exception
    
    return user

# Get a user but optional 
from fastapi.security.utils import get_authorization_scheme_param
from fastapi import Request

async def get_current_user_optional(
    request: Request,  # Use Request to manually extract token
    db: Session = Depends(get_db)
) -> Optional[models.User]:
    """
    Get the current authenticated user, or None if not authenticated.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None  # No auth header means no authentication

    scheme, token = get_authorization_scheme_param(auth_header)
    
    if not token or scheme.lower() != "bearer":
        return None  # Malformed or missing token

    try:
        payload = decode_token(token)  # Decode the JWT
        email: Optional[str] = payload.get("username")
        if not email:
            return None
        return db.query(models.User).filter(models.User.email == email).first()
    except JWTError:
        return None  # Invalid or expired token



async def get_current_active_user(
    current_user: models.User = Depends(get_current_user)
) -> models.User:
    """
    Get the current active user
    """
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account not verified"
        )
    return current_user

async def get_current_admin(
    current_user: models.User = Depends(get_current_user)
) -> models.User:
    """
    Get the current admin user
    """
    if current_user.role != models.UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized"
        )
    return current_user


def create_password_reset_token(email: str):
    """
    Create a password reset token with an expiration time.
    """
    expiration = datetime.now(timezone.utc) + timedelta(hours=1)
    payload = {
        'email': email,
        'exp': expiration
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token

def password_verify_token(token: str):
    """
    Verify the password reset token and check for expiration.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload['email']
    except jwt.ExpiredSignatureError:
        return None
    except jwt.JWTError:
        return None
    


def verify_email_token(token: str) -> str:
    try:
        # Decode the token and get the payload
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # print("Decoded payload:", payload)
        
        # Check if the token is expired
        exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        if exp_time < datetime.now(timezone.utc):
            
            return None  # Token expired
        
        print("Token is valid")
        return payload["email"]  # Return the payload if valid
    except jwt.ExpiredSignatureError:
        print("Token expired signature error")
        return None
    except jwt.JWTError as e:
        print("JWT error:", e)
        return None

def token_expiration(token:str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        return exp_time
    except jwt.JWTError:
        return None
    except jwt.ExpiredSignatureError:
        return None