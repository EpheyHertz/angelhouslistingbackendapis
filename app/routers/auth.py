from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File,Form,Request
from fastapi.security import  OAuth2PasswordBearer,OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app import models, schemas, config
import logging
import tempfile
import base64
import os
from typing import Optional
from app.database import get_db
from ..services.upload import upload_image
from app.services import oauth, email
from app.utils import hash_password, verify_password
import random
import string
from datetime import datetime, timedelta
from ..services.helper import resend_verification_code,resend_verification_link
import random

router = APIRouter(
    prefix="/users",
    tags=["Users"],
)
logger = logging.getLogger(__name__)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="users/login")




@router.post("/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user: schemas.UserCreate,request: Request, db: Session = Depends(get_db)):
    print(user)
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
        # print(user_data)
        user_data['password'] = hashed_password

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

        

        # Check if platform is mobile from the request URL params
        platform = request.query_params.get("platform", "").lower()

        if platform == "mobile":
            # Generate a verification code (6-digit code example)
            verification_code = ''.join(random.choices(string.digits, k=6))
            
            # Send the verification code via email
            try:
                email.send_verification_code(new_user.email, verification_code, username=new_user.username)
        
                

        # Create a new verification code entry in the VerificationCode table
                verification_code_entry = models.VerificationCode(
                        user_id=new_user.id,  # Assuming there's a user_id in the VerificationCode table
                        code=verification_code,
                        expiration_date=datetime.now() + timedelta(hours=1)  # Set expiration to 1 hour from now
                    )
                
                db.add(verification_code_entry)
                db.commit()


            except Exception as e:
                db.flush(new_user)
                raise HTTPException(status_code=500, detail="Unable to send verification code")
        else:
            # Send standard verification URL if the platform is not mobile
            try:
                email.send_verification_email(new_user.email, username=new_user.username)
                
            except Exception as e:
                
                db.flush(new_user)
                raise HTTPException(status_code=500, detail="Unable to send verification email")

        return new_user

    except Exception as e:
        
        raise HTTPException(status_code=500, detail="Internal server error")




# Resend Verification Route
@router.post("/resend-verification", response_model=dict, status_code=status.HTTP_200_OK)
async def resend_verification(user: schemas.EmailSchema, request: Request, db: Session = Depends(get_db)):
    # Get the user based on email
    existing_user = db.query(models.User).filter(models.User.email == user.email).first()

    if not existing_user:
        logger.warning(f"Attempt to resend verification for non-existent email: {user.email}")
        raise HTTPException(status_code=404, detail="User not found")

    # Get the platform from the request URL params
    platform = request.query_params.get("platform", "").lower()

    if platform == "mobile":
        # Resend the verification code for mobile platform
        return await resend_verification_code(existing_user, platform, db)
    else:
        # Resend the verification link for non-mobile platform
        return await resend_verification_link(existing_user, db)










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
    if not db_user.is_verified:
        raise HTTPException(status_code=403, detail="User not verified")

    # Generate access and refresh tokens
    try:
        access_token = oauth.create_access_token(data={"username": db_user.email, "user_id": db_user.id})
        refresh_token = oauth.create_refresh_token(data={"username": db_user.email, "user_id": db_user.id})
        expires_in=oauth.token_expiration(access_token)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating tokens: {str(e)}")

    return {"access_token": access_token, "refresh_token": refresh_token,"expires_in":expires_in, "token_type": "bearer"}

@router.get("/me", response_model=schemas.UserResponse, status_code=status.HTTP_200_OK)
def read_users_me(current_user: schemas.UserResponse = Depends(oauth.get_current_user)):
    return current_user


@router.get("/profile", response_model=schemas.UserResponse)
async def get_logged_in_user_profile(
    current_user: models.User = Depends(oauth.get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieve the profile of the currently logged-in user.
    """
    try:
        db_user = db.query(models.User).filter(models.User.id == current_user.id).first()
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
        return db_user
    except SQLAlchemyError as e:
        logging.error(f"Database error while retrieving profile for user ID {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail="An error occurred while retrieving the profile")
    except Exception as e:
        logging.error(f"Unexpected error while retrieving profile for user ID {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.get("/profile/{user_id}", response_model=schemas.UserResponse)
async def get_user_profile_by_id(
    user_id: int,
    current_user: models.User = Depends(oauth.get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieve the profile of a user by their ID.
    This route requires the requesting user to be authenticated.
    """
    try:
        db_user = db.query(models.User).filter(models.User.id == user_id).first()
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
        return db_user
    except SQLAlchemyError as e:
        logging.error(f"Database error while retrieving profile for user ID {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="An error occurred while retrieving the profile")
    except Exception as e:
        logging.error(f"Unexpected error while retrieving profile for user ID {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")

@router.post("/password-reset",status_code=status.HTTP_200_OK)
def request_password_reset(emailShema: schemas.EmailSchema, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == emailShema.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_verified:
        raise HTTPException(status_code=403, detail="User not verified")

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
            email.send_welcome_email(email=user.email, username=user.username,template_name='welcome_email.html')
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
    request: Request,
    username: Optional[str] = Form(None),
    full_name: Optional[str] = Form(None),
    contact_number: Optional[str] = Form(None),
    profile_picture: Optional[UploadFile] = File(None),
    location: Optional[str] = Form(None),
    id_document_url: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    zipcode: Optional[str] = Form(None),
    country: Optional[str] = Form(None),
    state: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    first_name: Optional[str] = Form(None),
    last_name: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth.get_current_user),
):

    # Retrieve and print the form data from the request
    form_data = await request.form()
    print(f"Received form data: {form_data}")

    # Optionally log the form data (without sensitive information)
    logging.info(f"Received form data: {form_data}")

    # Logging to check if the function is entered
    logging.info(f"Updating user profile for user ID {current_user.id}")

    # Retrieve current user from the database
    db_user = db.query(models.User).filter(models.User.id == current_user.id).first()

    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
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
        if address:
            db_user.address = address
        if zipcode:
            db_user.zipcode = zipcode
        if country:
            db_user.country = country
        if state:
            db_user.state = state
        if phone:
            db_user.phone_number = phone
        if phone:
            db_user.contact_number = phone
        if first_name:
            db_user.first_name = first_name
        if last_name:
            db_user.last_name = last_name

        # Handle image upload if new image is provided
        if profile_picture:
            try:
                # Upload image to cloud storage (adjust this function as needed)
                image_url = await upload_image(profile_picture)
                db_user.profile_image = image_url
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to upload profile image: {str(e)}")

        # Commit the changes to the database
        db.commit()

        # Refresh the db_user to reflect the updated data
        db.refresh(db_user)

        # Logging after successful update
        logging.info(f"User profile updated successfully for user ID {current_user.id}")

    except Exception as e:
        # Rollback the transaction in case of any error
        db.rollback()
        logging.error(f"Error updating profile for user ID {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update user profile")

    return db_user



@router.post("/mobile/verify-code", status_code=status.HTTP_200_OK)
async def verify_code(
    verification_data: schemas.VerificationCodeVerification, 
    db: Session = Depends(get_db)
):
    # Retrieve the verification code from the database
    verification_code = db.query(models.VerificationCode).filter(models.VerificationCode.code == verification_data.code).first()

    # If the code does not exist
    if not verification_code:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Verification code not found"
        )

    # If the code is expired
    if verification_code.is_expired():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code has expired"
        )

    # Retrieve the associated user
    user = db.query(models.User).filter(models.User.id == verification_code.user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Mark the user as verified
    user.is_verified = True
    db.commit()

    # Optionally, you could delete or invalidate the verification code after use
    db.delete(verification_code)
    db.commit()

    # Send a confirmation email (optional)
    try:
        email.send_welcome_email(email=user.email, username=user.username)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send confirmation email"
        )

    return {"message": "Verification successful"}




@router.post("/contact",status_code=status.HTTP_200_OK)
async def submit_contact(
    contact_data: schemas.ContactRequest,
    current_user: models.User = Depends(oauth.get_current_user)
):
    
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    
    print(current_user.email)
    try:
        # Send confirmation email to user
        random_number = random.randint(1000, 9999) 
        try:
                email.send_email(
                    to_email=current_user.email,
                    subject="We've Received Your Inquiry",
                    template_name="user_contact_confirmation.html",
                    random_number=random_number,
                    name= contact_data.name,
                    main_subject= contact_data.subject,
                    message= contact_data.message,
                    support_email="support@angelhousing.com"
                
                )
        except Exception as e:
           print(e)
           raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail=f'An error occured sending message to owner:{e}')
        
        # Send notification to support team
        try:
                email.send_email(
                    to_email=config.SMTP_USER,
                    subject=f"New Contact Request: {contact_data.subject}",
                    template_name="support_notification.html",
                    
                        user_name= contact_data.name,
                        user_email=contact_data.email,
                        user_main_email=current_user.email,
                        main_subject= contact_data.subject,
                        message= contact_data.message,
                        priority="High"
                
                )
        except Exception as e:
               print(e)
               raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail=f'An error occured sending message to support:{e}')

        return {"status": "success"}
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/verify/access_token",status_code=status.HTTP_200_OK)
async def verify_token(
    current_user: models.User = Depends(oauth.get_current_user)
):
    if not current_user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail='User not Authorised')
    return current_user