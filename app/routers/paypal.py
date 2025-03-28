from datetime import datetime, time
import logging
from typing import Optional
from fastapi import HTTPException, APIRouter, Depends, status
from sqlalchemy.orm import Session
import paypalrestsdk
from app.config import PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET, PAYPAL_MODE
from app.models import Transaction, TransactionType, User, TransactionStatus
from app.database import get_db
from app.schemas import (
    PayPalOrderCreateRequest,
    PayPalOrderCreateResponse,
    PayPalOrderCaptureRequest,
    PayPalOrderCaptureResponse
)
from app.services.oauth import get_current_user, get_current_user_optional
from app.services.invoice import send_invoice

# Configure PayPal SDK
paypalrestsdk.configure({
    "mode": PAYPAL_MODE,  # "sandbox" or "live"
    "client_id": PAYPAL_CLIENT_ID,
    "client_secret": PAYPAL_CLIENT_SECRET
})

router = APIRouter(prefix="/payments/paypal", tags=["PayPal Payments"])

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
@router.post("/create-order/", response_model=PayPalOrderCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_paypal_order(
    order_data: PayPalOrderCreateRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    try:
        # Log user status
        if current_user:
            logger.info(f"Creating PayPal order for authenticated user: {current_user.id}")
            user_id = current_user.id
        else:
            logger.info("Creating PayPal order for anonymous user")
            user_id = None

        # Create PayPal payment
        payment = paypalrestsdk.Payment({
            "intent": "sale",
            "payer": {
                "payment_method": "paypal"
            },
            "transactions": [{
                "amount": {
                    "total": str(order_data.amount),
                    "currency": order_data.currency.upper()
                },
                "description": order_data.description,
                "custom": str(user_id) if user_id else "anonymous",
                "invoice_number": f"INV-{int(datetime.now().timestamp())}",
                "item_list": {
                    "shipping_address": {
                        "recipient_name": order_data.name,
                        "line1": order_data.billing_address.street,
                        "city": order_data.billing_address.city,
                        "state": order_data.billing_address.state,
                        "postal_code": order_data.billing_address.postalCode,
                        "country_code": "KE"  # Default, can be parameterized
                    }
                }
            }],
            "redirect_urls": {
                "return_url": "https://digitaloceanapis.comradehomes.me/payment/success",
                "cancel_url": "https://digitaloceanapis.comradehomes.me/payment/cancel"
            }
        })

        if payment.create():
            logger.info(f"PayPal order created successfully: {payment.id}")
            
            # Extract the EC token from the approval URL
            approval_url = next(link.href for link in payment.links if link.rel == "approval_url")
            ec_token = approval_url.split('token=')[1]
            
            # Create pending transaction record
            transaction = Transaction(
                amount=order_data.amount,
                transaction_type=TransactionType.paypal,
                currency=order_data.currency,
                transaction_id=payment.id,
                description=order_data.description,
                status=TransactionStatus.PENDING,
                user_id=user_id,
                payment_metadata={
                    "email": order_data.email,
                    "name": order_data.name,
                    "billing_address": order_data.billing_address.model_dump(),
                    "ec_token": ec_token  # Store EC token in metadata
                }
            )
            db.add(transaction)
            db.commit()
            db.refresh(transaction)
            print("PAYPAL ORDER CREATED:", payment)
            
            logger.debug(f"PAYPAL ORDER CREATED: {payment}")

            return PayPalOrderCreateResponse(
                status="created",
                order_id=payment.id,
                approval_url=approval_url,
                transaction_id=transaction.id,
                ec_token=ec_token  # Include EC token in the response
            )
        else:
            error_msg = f"PayPal order creation failed: {payment.error}"
            logger.error(error_msg)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=payment.error
            )

    except Exception as e:
        logger.error(f"Unexpected error creating PayPal order: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating PayPal order"
        )

@router.post("/capture-order/", response_model=PayPalOrderCaptureResponse, status_code=status.HTTP_200_OK)
async def capture_paypal_order(
    capture_data: PayPalOrderCaptureRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    try:
        logger.info(f"Attempting to capture PayPal order: {capture_data.payment_id}")
        logger.info(f"Attempting to capture PayPal order with EC: {capture_data.order_id}")

        # Find the existing transaction
        transaction = db.query(Transaction).filter(
            Transaction.transaction_id == capture_data.payment_id
        ).first()

        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction not found"
            )

        # Execute payment
        payment = paypalrestsdk.Payment.find(capture_data.payment_id)
        
        if payment.execute({"payer_id": capture_data.payer_id}):
            logger.info(f"PayPal payment captured successfully: {payment.id}")

            # Update transaction status
            transaction.status = TransactionStatus.COMPLETED
            transaction.payment_metadata = {
                **transaction.payment_metadata,
                "capture_details": {
                    "payer_id": capture_data.payer_id,
                    "email": capture_data.email,
                    "capture_id": payment.transactions[0].related_resources[0].sale.id
                }
            }
            db.commit()

            # Prepare invoice data
            invoice_data = {
                'customer_name': (current_user.full_name if current_user else transaction.payment_metadata.get('name')),
                'customer_email': (current_user.email if current_user else capture_data.email),
                'invoice_number': transaction.id,
                'issue_date': transaction.created_at,
                'payment_by':transaction.transaction_type.value if hasattr(transaction.transaction_type, 'value') else transaction.transaction_type,
                'due_date': transaction.created_at,
                'service_description': transaction.description,
                'amount': transaction.amount*100,
                'currency': transaction.currency,
                'paypal_url': 'https://www.paypal.com/activity/payment/',
                'transaction_id': payment.id
            }

            try:
                send_invoice(invoice_data)
            except Exception as e:
                logger.error(f"Error sending PayPal invoice: {e}")

            return PayPalOrderCaptureResponse(
                status="completed",
                capture_id=payment.transactions[0].related_resources[0].sale.id,
                transaction_id=transaction.id,
                amount=transaction.amount,
                currency=transaction.currency
            )
        else:
            error_msg = f"PayPal payment capture failed: {payment.error}"
            logger.error(error_msg)
            
            # Update transaction status to failed
            transaction.status = TransactionStatus.FAILED
            db.commit()

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=payment.error
            )

    except HTTPException:
        raise  # Re-raise existing HTTP exceptions

    except Exception as e:
        logger.error(f"Unexpected error capturing PayPal payment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while capturing payment"
        )