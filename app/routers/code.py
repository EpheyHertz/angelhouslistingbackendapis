from fastapi import APIRouter

from .. import config
# from ..services.send_otp import send_verify_code, validate_code
from .. import schemas
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
import sendlk
from sendlk.responses import SmsResponse
from sendlk.exceptions import SendLKException
from sendlk.engine import SMS
from sendlk.options import SendLKVerifyOption, SendLKCodeTemplate
router=APIRouter(prefix="/code",tags=["Phone Verification"])

# Initialize the SendLK client
SENDLK_TOKEN = config.SENDLK_TOKEN
SENDLK_SECRET = config.SECRET_KEY

# Sender ID for SMS
SENDER_ID = config.SENDER_ID

# FastAPI app


# Custom template for verification SMS
class CustomCodeTemplate(SendLKCodeTemplate):
    def __init__(self):
        super().__init__()
    
    def text(self, code: str) -> str:
        return f"{code} is the verification code for your phone number used in Angel Housing Property"

# Options for the SMS verification process
options = SendLKVerifyOption(
    code_length=6,  # Length of the code
    expires_in=5,   # Expiration time in minutes
    sender_id=SENDER_ID,  # Sender ID
    subject="Phone Number Verification",  # Subject
    code_template=CustomCodeTemplate()  # Custom template
)

@router.post("/send-code", response_model=schemas.CodeResponse)
async def send_code(request: schemas.SendCodeRequest):
    """
    Sends a verification code to the provided phone number.
    """
    try:
        response: SmsResponse = SMS.send_verify_code(request.phone_number, options)
        token = response.data.get("token")
        if token:
            return schemas.CodeResponse(message="Verification code sent successfully.", success=True)
        else:
            raise HTTPException(status_code=500, detail="Failed to retrieve verification token.")
    except SendLKException as e:
        raise HTTPException(status_code=400, detail=f"Error: {str(e)}")

@router.post("/validate-code", response_model=schemas.CodeResponse)
async def validate_code(request: schemas.ValidateCodeRequest):
    """
    Validates the verification code with the provided token.
    """
    try:
        response: SmsResponse = SMS.validate_verify_code(request.code, request.token)
        if response.success:
            return schemas.CodeResponse(message="Code validated successfully.", success=True)
        else:
            raise HTTPException(status_code=400, detail="Invalid or expired verification code.")
    except SendLKException as e:
        raise HTTPException(status_code=400, detail=f"Error: {str(e)}")

