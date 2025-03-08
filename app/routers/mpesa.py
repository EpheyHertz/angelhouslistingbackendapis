import requests
import base64
import json
import re
import os
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request, Depends
from dotenv import load_dotenv
from slowapi import Limiter
from slowapi.util import get_remote_address
from app import schemas
from app.config import CONSUMER_KEY, CONSUMER_SECRET, MPESA_PASSKEY, MPESA_SHORTCODE, CALLBACK_URL, MPESA_BASE_URL,CALLBACK_URL_API_KEY

# Load environment variables
load_dotenv()
router = APIRouter(prefix="/mpesa", tags=["M-Pesa"])
limiter = Limiter(key_func=get_remote_address)
# Retrieve variables from the environment
# CONSUMER_KEY = os.getenv("CONSUMER_KEY")
# CONSUMER_SECRET = os.getenv("CONSUMER_SECRET")
# MPESA_PASSKEY = os.getenv("MPESA_PASSKEY")
# MPESA_SHORTCODE = os.getenv("MPESA_SHORTCODE")
# CALLBACK_URL = os.getenv("CALLBACK_URL")
# MPESA_BASE_URL = os.getenv("MPESA_BASE_URL")

# Phone number formatting and validation
def format_phone_number(phone: str) -> str:
    phone = phone.replace("+", "")
    if re.match(r"^254\d{9}$", phone):
        return phone
    elif phone.startswith("0") and len(phone) == 10:
        return "254" + phone[1:]
    else:
        raise HTTPException(status_code=400, detail="Invalid phone number format")

# Generate M-Pesa access token
def generate_access_token() -> str:
    try:
        credentials = f"{CONSUMER_KEY}:{CONSUMER_SECRET}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        headers = {"Authorization": f"Basic {encoded_credentials}", "Content-Type": "application/json"}
        response = requests.get(
            f"{MPESA_BASE_URL}/oauth/v1/generate?grant_type=client_credentials",
            headers=headers,
        ).json()
        if "access_token" in response:
            return response["access_token"]
        raise HTTPException(status_code=500, detail="Access token missing in response.")
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Failed to connect to M-Pesa: {str(e)}")

# Pydantic models for request validation


@router.post("/initiate-payment/")
def initiate_stk_push(payment_data: schemas.PaymentRequest):
    try:
        phone = format_phone_number(payment_data.phone_number)
        amount = payment_data.amount
        token = generate_access_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        stk_password = base64.b64encode((MPESA_SHORTCODE + MPESA_PASSKEY + timestamp).encode()).decode()
        request_body = {
            "BusinessShortCode": MPESA_SHORTCODE,
            "Password": stk_password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": amount,
            "PartyA": phone,
            "PartyB": MPESA_SHORTCODE,
            "PhoneNumber": phone,
            "CallBackURL": CALLBACK_URL,
            "AccountReference": "account",
            "TransactionDesc": "Payment for goods",
        }
        response = requests.post(
            f"{MPESA_BASE_URL}/mpesa/stkpush/v1/processrequest",
            json=request_body,
            headers=headers,
        ).json()
        print("Response:", response)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initiate STK Push: {str(e)}")

@router.post("/query-stk-status/")
def query_stk_push(request_data: schemas.STKQueryRequest):
    try:
        token = generate_access_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        password = base64.b64encode((MPESA_SHORTCODE + MPESA_PASSKEY + timestamp).encode()).decode()
        request_body = {
            "BusinessShortCode": MPESA_SHORTCODE,
            "Password": password,
            "Timestamp": timestamp,
            "CheckoutRequestID": request_data.checkout_request_id,
        }
        response = requests.post(
            f"{MPESA_BASE_URL}/mpesa/stkpushquery/v1/query",
            json=request_body,
            headers=headers,
        ).json()
        return response
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Error querying STK status: {str(e)}")



# Define allowed IP addresses
ALLOWED_IPS = {
    "196.201.214.200",
    "196.201.214.206",
    "196.201.213.114",
    "196.201.214.207",
    "196.201.214.208",
    "196.201.213.44",
    "196.201.212.127",
    "196.201.212.138",
    "196.201.212.129",
    "196.201.212.136",
    "196.201.212.74",
    "196.201.212.69",
}

async def verify_ip(request: Request):
    """Middleware-like dependency to check if the request's IP is allowed."""
    client_ip = request.client.host  # Extract client IP
    print("client_ip",client_ip)
    if client_ip not in ALLOWED_IPS:
        print(f"Unauthorized access attempt from {client_ip}")
        raise HTTPException(status_code=403, detail="Access denied: Unauthorized IP")
    return client_ip  # Return IP for logging/debugging if needed

@router.post("/payment-callback/{key}/")
@limiter.limit("5/minute")
async def payment_callback(request: Request,
                           key:str, client_ip: str = Depends(verify_ip)):
    if key != CALLBACK_URL_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    """Handles payment callbacks securely, only allowing requests from whitelisted IPs."""
    try:
        callback_data = await request.json()
        result_code = callback_data["Body"]["stkCallback"]["ResultCode"]
        print(f"Callback received from {client_ip}: {callback_data}")

        if result_code == 0:
            checkout_id = callback_data["Body"]["stkCallback"]["CheckoutRequestID"]
            metadata = callback_data["Body"]["stkCallback"]["CallbackMetadata"]["Item"]
            amount = next(item["Value"] for item in metadata if item["Name"] == "Amount")
            mpesa_code = next(item["Value"] for item in metadata if item["Name"] == "MpesaReceiptNumber")
            phone = next(item["Value"] for item in metadata if item["Name"] == "PhoneNumber")

            print(f"Payment successful - Checkout ID: {checkout_id}, Amount: {amount}, M-Pesa Code: {mpesa_code}, Phone: {phone}")
            return {"ResultCode": 0, "ResultDesc": "Payment successful"}

        return {"ResultCode": result_code, "ResultDesc": "Payment failed"}

    except (json.JSONDecodeError, KeyError) as e:
        print(f"Error processing request from {client_ip}: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid request data: {str(e)}")

