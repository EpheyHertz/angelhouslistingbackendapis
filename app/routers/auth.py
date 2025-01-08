from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File,Form
from fastapi.security import  OAuth2PasswordBearer,OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app import models, schemas
import logging
import tempfile
import base64
import os
from typing import Optional
from app.database import get_db
from ..services.upload import upload_image
from app.services import oauth, email
from app.utils import hash_password, verify_password

router = APIRouter(
    prefix="/users",
    tags=["Users"],
)
logger = logging.getLogger(__name__)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="users/login")

@router.post("/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    # Check if user already exists
    existing_user = db.query(models.User).filter(models.User.email == user.email).first()
    if existing_user:
        logger.warning(f"Attempt to register with already existing email: {user.email}")
        raise HTTPException(status_code=400, detail="Email already registered")

    try:
        # Hash the password
        hashed_password = hash_password(user.password)

        # Convert user data to a dictionary and replace the password
        user_data = user.model_dump()
        print(user_data)
        user_data['password'] = hashed_password

        # Decode Base64 image and save it as a temporary file
        # if user.profile_picture:
        #     image = user.profile_picture  # Ensure this is a base64-encoded string
        #     try:
        #         # Decode the base64 image
                
        #         # Upload the image
        #         image_url = await upload_image(image)
            
        #         user_data['profile_image'] = image_url

        #     except Exception as e:
        #         logger.error(f"Failed to process profile image: {str(e)}")
        #         raise HTTPException(status_code=400, detail="Invalid image format")

        # Capitalize the first letter of first_name and last_name
        first_name = user.first_name.strip().capitalize()
        last_name = user.last_name.strip().capitalize()

        # Combine first_name and last_name into full_name
        full_name = f"{first_name} {last_name}"
        user_data['full_name'] = full_name

        # Remove spaces from the username
        username = user.username.replace(" ", "")
        user_data['username'] = username

        # Format location as a string combining country and state
        location = f"{user.country}, {user.state}" if user.country and user.state else user.location
        user_data['location'] = location

        # Create new user instance
        new_user = models.User(**user_data)

        # Add user to DB and commit
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        logger.info(f"User registered successfully: {new_user.email}")

        # Send verification email
        try:
            email.send_verification_email(new_user.email, username=new_user.username)
            logger.info(f"Verification email sent to: {new_user.email}")
        except Exception as e:
            logger.error(f"Failed to send verification email to {new_user.email}: {str(e)}")
            raise HTTPException(status_code=500, detail="Unable to send verification email")

        return new_user

    except Exception as e:
        logger.error(f"Error during user registration: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# @router.post("/register", response_model=schemas.UserResponse)
# async def register(
#     user: schemas.UserCreate ,
#     profile_picture: UploadFile = File(...),
#     db: Session = Depends(get_db),
# ):
#     # Check if user already exists
#     existing_user = db.query(models.User).filter(models.User.email == user.email).first()
#     if existing_user:
#         logger.warning(f"Attempt to register with already existing email: {user.email}")
#         raise HTTPException(status_code=400, detail="Email already registered")
#     print(user)

#     try:
#         # Hash the password
#         hashed_password = hash_password(user.password)

#         # Convert user data to a dictionary and replace the password
#         user_data = user.model_dump()
#         user_data["password"] = hashed_password

#         # Process uploaded file
#         if profile_picture:
#             try:
#                 # Read file content
#                 content = await profile_picture.read()

#                 # Upload the image (you can replace `upload_image` with your actual upload logic)
#                 image_url = await upload_image(profile_picture)
#                 user_data["profile_image"] = image_url

#             except Exception as e:
#                 logger.error(f"Failed to process profile image: {str(e)}")
#                 raise HTTPException(status_code=400, detail="Invalid image format")

#         # Capitalize the first letter of first_name and last_name
#         first_name = user.first_name.strip().capitalize()
#         last_name = user.last_name.strip().capitalize()

#         # Combine first_name and last_name into full_name
#         full_name = f"{first_name} {last_name}"
#         user_data["full_name"] = full_name

#         # Remove spaces from the username
#         username = user.username.replace(" ", "")
#         user_data["username"] = username

#         # Format location as a string combining country and state
#         location = (
#             f"{user.country}, {user.state}" if user.country and user.state else user.location
#         )
#         user_data["location"] = location

#         # Create new user instance
#         new_user = models.User(**user_data)

#         # Add user to DB and commit
#         db.add(new_user)
#         db.commit()
#         db.refresh(new_user)

#         logger.info(f"User registered successfully: {new_user.email}")

#         # Send verification email
#         try:
#             email.send_verification_email(new_user.email, username=new_user.username)
#             logger.info(f"Verification email sent to: {new_user.email}")
#         except Exception as e:
#             logger.error(f"Failed to send verification email to {new_user.email}: {str(e)}")
#             raise HTTPException(status_code=500, detail="Unable to send verification email")

#         return new_user

#     except Exception as e:
#         logger.error(f"Error during user registration: {str(e)}")
#         raise HTTPException(status_code=500, detail="Internal server error")







@router.post("/login", response_model=schemas.Token, status_code=status.HTTP_200_OK)
def login(user: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Login route: authenticates a user and provides access and refresh tokens.
    """
    print("User:",user)
    print("Email:",user.username,"Password:", user.password)
    # Check if the user exists in the database
    db_user = db.query(models.User).filter(models.User.email == user.username).first()
    if not db_user or not verify_password(user.password, db_user.password):
        raise HTTPException(status_code=400, detail="Invalid credentials")

    # Generate access and refresh tokens
    try:
        access_token = oauth.create_access_token(data={"username": db_user.email, "user_id": db_user.id})
        refresh_token = oauth.create_refresh_token(data={"username": db_user.email, "user_id": db_user.id})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating tokens: {str(e)}")

    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}

@router.get("/me", response_model=schemas.UserResponse, status_code=status.HTTP_200_OK)
def read_users_me(current_user: schemas.UserResponse = Depends(oauth.get_current_user)):
    return current_user

@router.post("/password-reset",status_code=status.HTTP_200_OK)
def request_password_reset(emailShema: schemas.EmailSchema, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == emailShema.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Generate password reset token
    token = oauth.create_password_reset_token(user.email)
    email.send_password_reset_email(user.email, token)

    return {"detail": "Password reset email sent"}

@router.post("/password-reset/confirm",status_code=status.HTTP_200_OK)
def confirm_password_reset(token: str, password_reset: schemas.PasswordReset, db: Session = Depends(get_db)):
    try:
        email = oauth.password_verify_token(token)
        if not email:
            raise HTTPException(status_code=404, detail="User not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update user password
    hashed_password = hash_password(password_reset.new_password)
    user.password = hashed_password
    db.commit()

    # Generate new access token
    # access_token = oauth.create_access_token(data={"sub": user.email})
    # return {"access_token": access_token, "token_type": "bearer"}
    return {"detail": "Password reset successful"}



@router.get("/verify-email",status_code=status.HTTP_200_OK)
async def verify_email(
    email_data: schemas.VerificationToken = Depends(),  # Use the schema to validate the input
    db: Session = Depends(get_db),
):
    """
    Verifies the user's email using the provided token and email.
    Sets `is_verified` to True if the token is valid.
    """
    # print("Email", email_data.email, "Token", email_data.token)
    try:
        # Verify the token and email combination
        user_email = oauth.verify_email_token(email_data.token)
        # print(user_email)
        if user_email != email_data.email:
            raise HTTPException(status_code=400, detail="Invalid token or email does not match.")
        
        # Find the user by email
        user = db.query(models.User).filter(models.User.email == email_data.email).first()

        if not user:
            raise HTTPException(status_code=404, detail="User not found.")

        # Check if already verified
        if user.is_verified:
            raise HTTPException(status_code=200, detail="Email is already verified.")

            
        

        # Set the user's email as verified
        user.is_verified = True
        try:
    # Attempt to send the welcome email
            email.send_welcome_email(email=user.email, username=user.username)
        except Exception as e:
            # Log the exception details for debugging
            logger.error(f"Error sending welcome email to {user.email}: {str(e)}")
            
            # Raise an HTTPException with a 500 status code and a custom error message
            raise HTTPException(
                status_code=500,
                detail="There was an error sending the welcome email. Please try again later."
            )
        db.commit()
        db.refresh(user)
        
        logger.info(f"Email verified successfully for user: {email_data.email}")

        return {"message": "Email verification successful."}

    except Exception as e:
        logger.error(f"Error during email verification: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
    



@router.put("/update_profile", response_model=schemas.UserResponse)
async def update_user_profile(
    username: Optional[str] = Form(None),
    full_name: Optional[str] = Form(None),
    contact_number: Optional[str] = Form(None),
    profile_image: Optional[UploadFile] = File(None),
    location: Optional[str] = Form(None),
    id_document_url: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth.get_current_user),
):
    # Retrieve current user from the database
    db_user = db.query(models.User).filter(models.User.id == current_user.id).first()

    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update user details
    if username:
        db_user.username = username
    if full_name:
        db_user.full_name = full_name
    if contact_number:
        db_user.contact_number = contact_number
    if location:
        db_user.location = location
    if id_document_url:
        db_user.id_document_url = id_document_url

    # Handle image upload if new image is provided
    if profile_image:
        try:
            # Upload image to cloud storage (adjust this function as needed)
            image_url = await upload_image(profile_image)
            db_user.profile_image = image_url
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to upload profile image: {str(e)}")

    # Commit the changes to the database
    db.commit()
    db.refresh(db_user)

    return db_user