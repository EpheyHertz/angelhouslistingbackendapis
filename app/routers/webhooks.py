# app/routers/webhooks.py
from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from app.services.email import send_webhook_email
from app.config import SECRET_KEY

router = APIRouter(
    prefix="/webhooks",
    tags=["webhooks"],
    responses={404: {"description": "Not found"}},
)

class WebhookPayload(BaseModel):
    event: str
    data: dict
    timestamp: Optional[str] = None

def verify_webhook_secret(request: Request):
    """Dependency to verify webhook secret"""
    if SECRET_KEY:
        secret_header = request.headers.get("X-Webhook-Secret")
        if secret_header != SECRET_KEY:
            raise HTTPException(status_code=403, detail="Invalid webhook secret")
    return True

@router.post("/notifications")
async def handle_notification_webhook(
    payload: WebhookPayload,
    request: Request,
    verified: bool = Depends(verify_webhook_secret)
):
    """
    Handle incoming webhook notifications for important events.
    
    Example payload:
    {
        "event": "payment.received",
        "data": {"amount": 100, "currency": "USD"},
        "timestamp": "2023-01-01T00:00:00Z"
    }
    """
    event = payload.event
    
    # Customize these events based on what you need to monitor
    monitored_events = {
        "PAYMENT.CAPTURE.REFUNDED": "A payment was Refunded by Your Company",
        "PAYMENT.CAPTURE.COMPLETED": "A payment was Completed by Paypal",
        "PAYMENT.CAPTURE.REVERSED": "A payment was Reversed by Paypal",
        "PAYMENT.CAPTURE.DECLINED": "A new payment was Declined by User",
        "PAYMENTS.PAYMENT.CREATED": "A new payment was Created",
        "INVOICING.INVOICE.PAID": "Invoice Paid",
        "user.signup": "New User Signup",
        "error.occurred": "System Error Occurred"
    }
    
    if event in monitored_events:
        subject = f"⚠️ {monitored_events[event]} - {event}"
        body = f"""
        New event notification:
        
        Event Type: {event}
        Event Title: {monitored_events[event]}
        
        Details:
        {payload.data}
        
        Timestamp: {payload.timestamp}
        """
        
        if send_webhook_email(event_type=event, event_data=payload.data):
            return {
                "status": "success",
                "message": "Notification processed and email sent",
                "event": event
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to send email notification"
            )
    
    return {
        "status": "ignored",
        "message": "Event not configured for notifications",
        "event": event
    }