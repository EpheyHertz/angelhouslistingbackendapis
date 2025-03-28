import logging
from typing import Optional
from fastapi import HTTPException, APIRouter, Depends, status
from sqlalchemy.orm import Session
import stripe
from app.config import TEST_STRIPE_PUBLIC_KEY, TEST_STRIPE_SECRET_KEY
from app.models import Transaction, TransactionType,User,TransactionStatus
from app.database import get_db
from app.schemas import PaymentRequestStripe, PaymentResponseStripe
from app.services.oauth import get_current_user,get_current_user_optional
from app.services.invoice import send_invoice

# Configure Stripe with your secret key
stripe.api_key = TEST_STRIPE_SECRET_KEY

router = APIRouter(prefix="/payments", tags=["Stripe Payments"])

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



@router.post("/process-payment/", response_model=PaymentResponseStripe, status_code=status.HTTP_200_OK)
async def process_payment(
    payment: PaymentRequestStripe, 
   current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    try:
        # Log user status (authenticated or anonymous)
        if current_user:
            logger.info(f"Processing payment for authenticated user: {current_user.id}")
            user_id = current_user.id
        else:
            logger.info("Processing payment for anonymous user")
            user_id = None

        # Create a charge using the Stripe API
        if payment.currency.lower() == 'kes':
            payment.amount = payment.amount * 100
        charge = stripe.Charge.create(
            amount=payment.amount,
            currency=payment.currency,
            source=payment.token,  # Stripe token obtained from the client-side
            description="Payment for Comrade Homes",
        )

        # Save to the database
        transaction = Transaction(
            amount=payment.amount,
            transaction_type=TransactionType.stripe,
            currency=payment.currency,
            transaction_id=charge.id,
            description="Payment for Comrade Homes",
            status=TransactionStatus.COMPLETED,
            user_id=user_id  # Add user_id if user is authenticated
        )
        db.add(transaction)
        db.commit()
        db.refresh(transaction)
        
        invoice_data = {
            'customer_name': (current_user.full_name if current_user and current_user.full_name else payment.name),
            'customer_email': (current_user.email if current_user and current_user.email else payment.email),
            'invoice_number': transaction.id,
            'issue_date': transaction.created_at,
            'due_date': transaction.created_at,
            'service_description': transaction.description,
            'amount':transaction.amount,
            'payment_by':transaction.transaction_type,
            'currency': transaction.currency,
            'stripe_url': 'https://comradehomes.me/',
            'mpesa_url': 'https://comradehomes.me/'
        }
        try:
            # Send invoice via email
            send_invoice(invoice_data)
        except Exception as e:
            logger.error(f"Error sending invoice: {e}")

        # Log the successful transaction
        logger.info(f"Payment successful: {charge.id}")

        # Return a success response
        return PaymentResponseStripe(
            status="success",
            charge_id=charge.id,
            transaction_id=transaction.id
        )

    except stripe.error.CardError as e:
        # Handle specific Stripe errors (e.g., card declined)
        logger.error(f"Card error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

    except stripe.error.StripeError as e:
        # Handle generic Stripe errors
        logger.error(f"Stripe error: {str(e)}")
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again later.")

    except Exception as e:
        # Handle any other unexpected errors
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred. Please try again later.")