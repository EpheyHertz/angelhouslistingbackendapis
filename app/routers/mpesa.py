from typing import Optional
import requests
import base64
import json
import re
import os
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from dotenv import load_dotenv
from slowapi import Limiter
from slowapi.util import get_remote_address
from app import schemas
from app.config import CONSUMER_KEY, CONSUMER_SECRET, MPESA_PASSKEY, MPESA_SHORTCODE, CALLBACK_URL, MPESA_BASE_URL,CALLBACK_URL_API_KEY,MPESA_PARTY_B
from app.models import User,Transaction,TransactionType,TransactionStatus
from app.services.invoice import send_invoice
from app.services.oauth import get_current_user_optional


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
            print("Token:", response["access_token"])
            return response["access_token"]
        raise HTTPException(status_code=500, detail="Access token missing in response.")
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Failed to connect to M-Pesa: {str(e)}")

# Pydantic models for request validation


@router.post("/initiate-payment/")
def initiate_stk_push(
    payment_data: schemas.PaymentRequest, 
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
   
):
    if current_user:
        print(f"Processing payment for authenticated user: {current_user.id}")
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

        print("M-Pesa Response:", response)  # Debugging

        # Validate response
        if response.get("ResponseCode") != "0":
            raise HTTPException(status_code=400, detail="M-Pesa request failed.")

        # Extract M-Pesa transaction details
        merchant_request_id = response.get("MerchantRequestID")
        checkout_request_id = response.get("CheckoutRequestID")

  

        try:
            # Save transaction in the database
            transaction = Transaction(
                amount=amount,
                transaction_type=TransactionType.mpesa,  # Assuming you have an enum for M-Pesa
                currency="KES",
                transaction_id=checkout_request_id,  # Store STK Push ID
                description="Payment for Comrade Homes",
                status=TransactionStatus.PENDING,  # Set to pending, will be updated later
                user_id=current_user.id if current_user else None
            )
            db.add(transaction)
            db.commit()
            db.refresh(transaction)
            
            return {
                "message": "STK Push request sent successfully",
                "merchant_request_id": merchant_request_id,
                "checkout_request_id": checkout_request_id,
                "customer_message": response.get("CustomerMessage")
            }
        except Exception as e:
            # Rollback the transaction if there was an error
            db.rollback()
            print(f"Database error while saving transaction: {str(e)}")
            
            # Return an error response to the client
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to save transaction details: {str(e)}"
            )

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

        result_code = response.get("ResultCode")
        result_desc = response.get("ResultDesc", "Unknown error")

        error_responses = {
            "1037": "DS timeout: User cannot be reached.",
            "1025": "System error occurred while sending the push request.",
            "9999": "Error occurred while sending a push request.",
            "1032": "Request was canceled by the user.",
            "1": "Insufficient balance for the transaction.",
            "2001": "Invalid initiator information.",
            "1019": "Transaction has expired.",
            "1001": "Transaction already in process for this subscriber."
        }

        if result_code == "0":
            return {"message": "STK query successful", "response": response}

        error_message = error_responses.get(result_code, f"Unknown error: {result_desc}")
        raise HTTPException(status_code=400, detail=error_message)

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
async def payment_callback(
    request: Request,
    key: str,
    client_ip: str = Depends(verify_ip),
    db: Session = Depends(get_db)
):
    if key != CALLBACK_URL_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    
    try:
        callback_data = await request.json()
        result_code = callback_data["Body"]["stkCallback"]["ResultCode"]
        print(f"Callback received from {client_ip}: {callback_data}")
        
        # Extract CheckoutRequestID
        checkout_id = callback_data["Body"]["stkCallback"]["CheckoutRequestID"]
        
        # Fetch transaction from database
        transaction = db.query(Transaction).filter(Transaction.transaction_id == checkout_id).first()
        
        if not transaction:
            print(f"Transaction not found for Checkout ID: {checkout_id}")
            return {"ResultCode": 1, "ResultDesc": "Transaction not found"}
        
        if result_code == 0:
            # Extract payment metadata
            metadata = callback_data["Body"]["stkCallback"]["CallbackMetadata"]["Item"]
            amount = next(item["Value"] for item in metadata if item["Name"] == "Amount")
            mpesa_code = next(item["Value"] for item in metadata if item["Name"] == "MpesaReceiptNumber")
            phone = next(item["Value"] for item in metadata if item["Name"] == "PhoneNumber")
            
            # Update transaction details
            transaction.status = TransactionStatus.COMPLETED
            db.commit()
            
            print(f"Payment successful - Checkout ID: {checkout_id}, Amount: {amount}, M-Pesa Code: {mpesa_code}, Phone: {phone}")
            
            # Fetch user if available
            user = None
            if transaction.user_id:
                user = db.query(User).filter(User.id == transaction.user_id).first()
                
                # Only send invoice email if user exists
                if user:
   
                    # Prepare invoice data
                    invoice_data = {
                        'customer_name': user.full_name,
                        'customer_email': user.email,
                        'invoice_number': transaction.id,
                        'issue_date': transaction.created_at,
                        'due_date': transaction.created_at,
                        'service_description': transaction.description,
                        'amount': transaction.amount,
                        'currency': transaction.currency,
                        'mpesa_url': 'https://comradehomes.me/',
                        'stripe_url': 'https://comradehomes.me/',
                    }
                    
                    # Send invoice email
                    try:
                        send_invoice(invoice_data)  # Implement this function separately
                        print("Invoice email sent successfully.")
                    except Exception as e:
                        print(f"Error sending invoice email: {str(e)}")
            else:
                print("No user associated with this transaction. Invoice email not sent.")
            
            return {"ResultCode": 0, "ResultDesc": "Payment successful"}
        
        return {"ResultCode": result_code, "ResultDesc": "Payment failed"}
    
    except (json.JSONDecodeError, KeyError) as e:
        print(f"Error processing request from {client_ip}: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid request data: {str(e)}")
