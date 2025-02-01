import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List
from app.config import SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASSWORD
from jinja2 import Environment, FileSystemLoader
import jwt
import os
import logging
from datetime import datetime, timedelta
from app.config import SECRET_KEY
from typing  import Optional

from app import models
env = Environment(loader=FileSystemLoader('app/templates'))

def send_email(to_email: str, subject: str, template_name: str, **template_vars):
    """
    Send an email using the specified template and variables
    """
    # Get template
    template = env.get_template(template_name)
    html_content = template.render(**template_vars)

    # Create message
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = SMTP_USER
    msg['To'] = to_email

    # Add HTML content
    html_part = MIMEText(html_content, 'html')
    msg.attach(html_part)

    # Send email
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        print(f"Failed to send email: {str(e)}")
        raise

def send_bulk_email(
    to_emails: List[str], 
    subject: str, 
    template_name: Optional[str] = "send_bulk_emails.html", 
    batch_size: int = 50, 
    **template_vars
):
    """
    Send an email to multiple recipients using the specified template and variables.

    Args:
        to_emails (List[str]): List of recipient email addresses.
        subject (str): Subject of the email.
        template_name (str): Name of the email template file.
        batch_size (int): Number of emails to send in one batch. Default is 50.
        template_vars (dict): Variables for rendering the email template.
    """
    success_count = 0
    failure_count = 0
    failed_emails = []

    # Get template
    template = env.get_template(template_name)
    
    try:
        # Set up the SMTP server and login
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)

            # Sending emails in batches
            for i in range(0, len(to_emails), batch_size):
                batch_emails = to_emails[i:i + batch_size]
                for email in batch_emails:
                    try:
                        # Render email content from template, without passing 'subject' to template
                        html_content = template.render(**template_vars)

                        # Create the email message
                        msg = MIMEMultipart('alternative')
                        msg['Subject'] = subject  # Add subject here directly
                        msg['From'] = SMTP_USER
                        msg['To'] = email

                        # Attach the HTML content
                        html_part = MIMEText(html_content, 'html')
                        msg.attach(html_part)

                        # Send the email
                        server.send_message(msg)
                        success_count += 1
                    except Exception as e:
                        failure_count += 1
                        failed_emails.append(email)
                        print(f"Failed to send email to {email}: {str(e)}")

            # Print results
            print(f"Successfully sent {success_count} emails.")
            if failure_count > 0:
                print(f"Failed to send {failure_count} emails. See the failed list: {failed_emails}")

    except Exception as e:
        print(f"Failed to send bulk emails: {str(e)}")
        raise
def send_verification_email(email: str,username:str):
    """
    Send verification email to user
    """
    # Create verification token
    token = create_verification_token(email)
    verification_url = f"https://angelhouslistingwebsite.vercel.app/verify-email?token={token}&email={email}"
    username_caps = username.upper()

    send_email(
        to_email=email,
        username=username_caps,
        subject="Verify your email",
        template_name="email_verification.html",
        verification_url=verification_url
    )

logger = logging.getLogger(__name__)

def send_verification_code(email,verification_code,username, template_name: Optional[str]='verification_code_email.html'):
       username_caps = username.upper()
       send_email(
              to_email=email,
              username=username_caps,
              template_name=template_name,
              subject="Verification Code",
              verification_code=verification_code,

       )
       



def send_password_reset_email(email: str, token: str):
    """
    Send a password reset email to the user with a reset URL containing the token and email.
 
    Args:
        email (str): The recipient user's email address.
        token (str): The password reset token for the user.

    Returns:
        None: Sends an email. Raises an HTTPException if the email cannot be sent.
    """
    try:
        # Retrieve the base URL from environment variables for production or local settings
        base_url = os.getenv("BASE_URL", "https://angelhouslistingwebsite.vercel.app/")  # Default to localhost for dev
        
        # Include both the token and email in the reset URL
        reset_url = f"{base_url}auth/password-reset?token={token}&email={email}"

        # Send the email
        send_email(
            to_email=email,
            subject="Reset your password",
            template_name="password_reset.html",
            reset_url=reset_url  # Pass reset URL to the template
        )

        logger.info(f"Password reset email sent to {email}")

    except Exception as e:
        # Log the error and raise an HTTPException if email sending fails
        logger.error(f"Failed to send password reset email to {email}: {str(e)}")
        return None

def send_house_approval_email(email: str, house_title: str, is_approved: bool):
    """
    Send house approval/rejection notification to owner
    """
    status = "approved" if is_approved else "rejected"
    
    send_email(
        to_email=email,
        subject=f"House Listing {status.capitalize()}",
        template_name="house_approval.html",
        house_title=house_title,
        status=status
    )

def create_verification_token(email: str) -> str:
    """
    Create a JWT token for email verification
    """
    expiration = datetime.now() + timedelta(hours=24)
    return jwt.encode(
        {"email": email, "exp": expiration},
        SECRET_KEY,
        algorithm="HS256"
    )

def create_password_reset_token(email: str) -> str:
    """
    Create a JWT token for password reset
    """
    expiration = datetime.now(datetime.timezone.utc) + timedelta(hours=1)
    return jwt.encode(
        {"email": email, "exp": expiration},
        SECRET_KEY,
        algorithm="HS256"
    )

def verify_token(token: str) -> str:
    """
    Verify a JWT token and return the email
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload["email"]
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired")
    except jwt.JWTError:
        raise ValueError("Invalid token")


def send_welcome_email(username: str, email: str, template_name: Optional[str] = "welcome_email.html"):
    # Convert username to uppercase
    username_caps = username.upper()

    # Debugging logs
    print(f"Username (caps): {username_caps}, Email: {email}, Template: {template_name}")

    # Call the send_email function
    send_email(
        to_email=email,
        subject="Welcome to our platform",
        template_name=template_name,
        username=username_caps
    )
def send_created_house(email: str, subject: str, template_name: str, **template_vars):
    send_email(to_email=email,
               subject=subject,
               template_name=template_name,
               **template_vars)
    

def send_booking_email_to_owner(to_email:str,subject:str,template_name: str, **template_vars):
    send_email(to_email=to_email,
               subject=subject,
               template_name=template_name,
               **template_vars)
    

def send_booking_email_to_booker(to_email:str,subject:str,template_name: str, **template_vars):
                        send_email(to_email=to_email,
               subject=subject,
               template_name=template_name,
               **template_vars)
                        

def send_cancellation_email(to_email:str,subject:str,template_name: str, **template_vars):
                        send_email(to_email=to_email,
               subject=subject,
               template_name=template_name,
               **template_vars)
                        

def send_booking_approved_email(to_email:str,subject:str,template_name: str, **template_vars):
                        send_email(to_email=to_email,
               subject=subject,
               template_name=template_name,
               **template_vars)
                        
def send_booking_cancellation_email(to_email:str,subject:str,template_name: str, **template_vars):
                        send_email(to_email=to_email,
               subject=subject,
               template_name=template_name,
               **template_vars)
                        

def send_house_reject_email(to_email:str,subject:str,template_name: str, **template_vars):
                        send_email(to_email=to_email,
               subject=subject,
               template_name=template_name,
               **template_vars)

def send_appeal_confirmation_email_to_booking_owner(to_email:str,subject:str,template_name:str,**template_vars):
            send_email(to_email=to_email,
               subject=subject,
               template_name=template_name,
               **template_vars)                      
def send_appeal_confirmation_email_to_booking_house_owner(to_email:str,subject:str,template_name:str,**template_vars):
            send_email(to_email=to_email,
               subject=subject,
               template_name=template_name,
               **template_vars)                    


async def send_house_notification_email(admin_emails, owner_email, owner_username, **template_vars):
    print(template_vars)
    """
    Sends an email with house details to the owner and all admins.
    
    :param house_details: Dictionary containing house information
    :param admin_emails: List of admin emails
    :param owner_email: Email address of the house owner
    :param owner_username: Username of the house owner
    :param template_vars: Additional variables to pass to the email template
    """
    try:
        # Convert house details to a dictionary if it's a m

        # Send email to owner
        send_email(
            to_email=owner_email,
            subject="Your House Listing",
            username=owner_username,
            template_name="owner_house_creation.html",
          
            **template_vars
        )

        # Send email to admins
        admin_email_list = [admin for admin in admin_emails]
        send_email(
            to_email=", ".join(admin_email_list),  # Convert list to a string
            subject="New House Listing Added",
            template_name="admin_house_creation.html",
            **template_vars
        )

    except Exception as e:
        print(f"Error sending house notification emails: {str(e)}")
