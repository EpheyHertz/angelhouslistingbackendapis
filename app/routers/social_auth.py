from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.orm import Session
import logging
import random
import string
from app import models, schemas
from app.database import get_db
from app.services import oauth,email
from ..config import SECRET_KEY
from app.auth_config import mobile_config
from google.oauth2 import id_token
from google.auth.transport import requests
from app.config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
from authlib.integrations.starlette_client import OAuth
from fastapi.responses import RedirectResponse
from typing import Optional
from app.services import oauth
import requests
from ..services.email import send_welcome_email
# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth",tags=["Google Auth"])


# config_data = {
#     'GOOGLE_CLIENT_ID': GOOGLE_CLIENT_ID,
#     'GOOGLE_CLIENT_SECRET': GOOGLE_CLIENT_SECRET,
# }

# # Initialize OAuth
# oauth_client = OAuth()

# # Register Google client
# oauth_client.register(
#     name='google',
#     client_id=config_data['GOOGLE_CLIENT_ID'],
#     client_secret=config_data['GOOGLE_CLIENT_SECRET'],
#     server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
#     client_kwargs={'scope': 'openid email profile'},
# )

# # Helper function to generate a random state
# def generate_state(length=16):
#     """Generate a random string for OAuth state."""
#     return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

# Example usage in route
# @router.get('/auth/google')
# async def login_google(request: Request):
#     """
#     Redirect to Google for OAuth login.
#     """
#     state = generate_state()
#     request.session['oauth_state'] = state  # Save state in session
#     redirect_uri = 'http://localhost:8000/auth/callback/google'
#     return await oauth_client.google.authorize_redirect(request, redirect_uri, state=state)
# # Configure OAuth for Google
# oauth_client = OAuth()
# oauth_client.register(
#     name="google",
#     client_id=GOOGLE_CLIENT_ID,
#     client_secret=GOOGLE_CLIENT_SECRET,
#     server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
#     client_kwargs={"scope": "openid email profile"},
#     authorize_state=SECRET_KEY,
# )

# GOOGLE_REDIRECT_URI = "http://localhost:8000/auth/callback/google"
# FRONTEND_URL = "http://localhost:3000"

# oauth_client = OAuth()
# oauth_client.register(
#     name="google",
#     client_id=GOOGLE_CLIENT_ID,
#     client_secret=GOOGLE_CLIENT_SECRET,
#     server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
#     client_kwargs={"scope": "openid email profile"},
# )
GOOGLE_REDIRECT_URI = "https://angelhouslistingbackendapis.onrender.com/auth/callback/google"
FRONTEND_URL = "https://angelhouslistingwebsite.vercel.app/"  # Update this to match your frontend URL


# @router.get("/google")
# async def login_google(request: Request):
#     """Redirects user to Google for authentication."""
#     return  await oauth_client.google.authorize_redirect(request, GOOGLE_REDIRECT_URI)



@router.get("/google")
async def login_google():
    """
    Redirect the user to Google's OAuth page for login.
    """
    url = (
        f"https://accounts.google.com/o/oauth2/auth?"
        f"response_type=code&client_id={GOOGLE_CLIENT_ID}&redirect_uri={GOOGLE_REDIRECT_URI}&"
        f"scope=openid%20profile%20email&access_type=offline"
    )
    return RedirectResponse(url=url)

# @router.get("/callback/google")
# async def auth_google(
#     request: Request,
#     platform: Optional[str] = Query(None),
#     db: Session = Depends(get_db)
# ):
#     """
#     Handles Google OAuth callback and generates tokens.
#     Supports both web and mobile authentication flows.
#     """
#     try:
#         # print("Callback Request Params:", request.query_params)

#         # Authorize and fetch user details
#         user_response = await oauth_client.google.authorize_access_token(request)
#         # print("Google Token Response:", user_response)
#         user_info = user_response.get("userinfo")
#         # print("Google User Info:", user_info)
        
#         if not user_info:
#             logger.error("Failed to retrieve user info from Google")
#             raise HTTPException(status_code=401, detail="Failed to retrieve user info from Google")

#         # Access the 'userinfo' dictionary
#         google_user_info = user_info
#         if not google_user_info:
#             logger.error("No user info found in the Google response")
#             raise HTTPException(status_code=401, detail="No user info found in the Google response")

#         # Extract the relevant user information from the response
#         email = google_user_info.get("email")
#         full_name = google_user_info.get("name")
#         username = full_name.replace(' ', '_').lower() if full_name else email.split('@')[0]  # Fallback to email if no name
#         social_auth_id = google_user_info.get("sub")  # Google user identifier
#         verified=google_user_info.get("email_verified")
#         picture=google_user_info.get("picture")

#         if not email or not social_auth_id:
#             logger.error("Missing essential user info (email or social_auth_id)")
#             raise HTTPException(status_code=400, detail="Missing essential user info from Google")

#         # Check if user exists
#         user = db.query(models.User).filter(models.User.email == email).first()

#         if not user:
#             # Create new user
#             user = models.User(
#                 username=username,
#                 full_name=full_name,
#                 email=email,
#                 social_auth_provider=models.SocialAuthProvider.google,
#                 social_auth_id=social_auth_id,
#                 is_verified=verified,
#                 profile_image=picture,
#                 contact_number='',
#                 location=''
#             )
#             db.add(user)
#             db.commit()
#             db.refresh(user)
#             try:
#     # Attempt to send the welcome email
#                send_welcome_email(email=user.email, username=user.full_name)
#             except Exception as e:
#             # Log the exception details for debugging
#                 logger.error(f"Error sending welcome email to {user.email}: {str(e)}")
            
#             # Raise an HTTPException with a 500 status code and a custom error message
#                 raise HTTPException(
#                 status_code=500,
#                 detail="There was an error sending the welcome email. Please try again later."
#                )
#             logger.info(f"New user created via Google: {user.email}")
#         else:
#             logger.info(f"User authenticated: {user.email}")

#         # Generate access and refresh tokens
#         access_token = oauth.create_access_token(data={"username": user.email, "user_id": user.id})
#         refresh_token = oauth.create_refresh_token(data={"username": user.email, "user_id": user.id})

#         # Handle mobile redirect if platform is specified
#         if platform:
#             redirect_url = mobile_config.get_mobile_redirect_url(platform, access_token, refresh_token, "bearer")
#             logger.info(f"Redirecting to mobile app: {platform}")
#         else:
#             redirect_url = f"{FRONTEND_URL}/auth/oauth?access_token={access_token}&refresh_token={refresh_token}&token_type=bearer"
#             logger.info("Redirecting to web frontend")

#         return RedirectResponse(url=redirect_url)

#     except Exception as e:
#         logger.error(f"OAuth Error: {str(e)}")
#         raise HTTPException(status_code=401, detail=f"OAuth Error: {str(e)}")


@router.get("/callback/google")
async def auth_google(
    code: str, platform: Optional[str] = Query(None), db: Session = Depends(get_db)
):
    """
    Handle Google OAuth callback.
    """
    token_url = "https://accounts.google.com/o/oauth2/token"
    data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    try:
        # Exchange the code for tokens
        response = requests.post(token_url, data=data)
        response_data = response.json()

        if "access_token" not in response_data:
            raise HTTPException(status_code=400, detail="Failed to retrieve access token")

        access_token = response_data["access_token"]
        id_token = response_data.get("id_token")

        # Retrieve user information
        user_info = requests.get(
            "https://www.googleapis.com/oauth2/v1/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        ).json()

        email = user_info.get("email")
        full_name = user_info.get("name")
        username = full_name.replace(" ", "_").lower() if full_name else email.split("@")[0]
        social_auth_id = user_info.get("id")
        picture = user_info.get("picture")

        if not email or not social_auth_id:
            raise HTTPException(status_code=400, detail="Invalid user information from Google")

        # Check if the user exists in the database
        user = db.query(models.User).filter(models.User.email == email).first()
        if not user:
            # Create a new user
            user = models.User(
                username=username,
                full_name=full_name,
                email=email,
                social_auth_provider=models.SocialAuthProvider.google,
                social_auth_id=social_auth_id,
                is_verified=user_info.get("verified_email", False),
                profile_image=picture,
            )
            db.add(user)
            db.commit()
            db.refresh(user)

            # Send welcome email
            try:
                send_welcome_email(email=user.email, username=user.full_name)
            except Exception as e:
                logger.error(f"Failed to send welcome email: {e}")

            logger.info(f"New user registered: {email}")
        else:
            logger.info(f"User logged in: {email}")

        # Generate access and refresh tokens
        access_token = oauth.create_access_token(data={"username": user.email, "user_id": user.id})
        refresh_token = oauth.create_refresh_token(data={"username": user.email, "user_id": user.id})

        # Construct the redirect URL
        if platform:
             redirect_url = mobile_config.get_mobile_redirect_url(platform, access_token, refresh_token, "bearer")
             logger.info(f"Redirecting to mobile app: {platform}")
             return {'access_token':access_token,'refresh_token':refresh_token}
        else:             
            redirect_url = f"{FRONTEND_URL}/auth/oauth?access_token={access_token}&refresh_token={refresh_token}&token_type=bearer"
            logger.info("Redirecting to web frontend")

        
            return RedirectResponse(url=redirect_url)
    except Exception as e:
        logger.error(f"Google OAuth Error: {e}")
        raise HTTPException(status_code=500, detail="Authentication failed")
