import json
from fastapi import APIRouter, HTTPException, Depends,status
from typing import List,Optional
import httpx
from pydantic import BaseModel
import requests
from sqlalchemy.orm import Session
from sqlalchemy import alias, func
from datetime import datetime, timedelta

from upstash_workflow import AsyncWorkflowContext
from app.database import get_db
from app import models,schemas
from app.models import Booking, Cart, House, User,Like,Review
import logging
from app.schemas import BookingCreate, CartAdd, BookingResponse, CartResponse,CartSearchResponse
from app.config import QSTASH_TOKEN, QSTASH_URL,QSTASH_CURRENT_SIGNING_KEY,QSTASH_NEXT_SIGNING_KEY
from ..services.email import send_email,send_booking_email_to_owner,send_booking_email_to_booker,send_booking_approved_email,send_booking_cancellation_email  # Custom utility to send emails
from ..services.oauth import get_current_user,get_current_admin
from sqlalchemy.exc import SQLAlchemyError
from typing import Dict, Any
from qstash import AsyncQStash
from app.routers.workflows import call_trigger_reminders



router = APIRouter(prefix="/houses", tags=["Houses"])

from sqlalchemy.orm import aliased

# @router.get("/cart", response_model=List[CartSearchResponse])
@router.get("/cart",status_code=status.HTTP_200_OK)
def get_cart_items(
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Fetch all houses in the current user's cart with optional search functionality.
    Includes house fields, owner details, like count, review count, and detailed reviews.
    """
    # Alias for the second User table join (reviewer)
    Reviewer = aliased(User)

    query = (
        db.query(
            Cart.id.label("cart_id"),
            Cart.added_at,
            House.id.label("house_id"),
            House.title,
            House.description,
            House.price,
            House.location,
            House.room_count,
            House.amenities,
            House.image_urls,
            func.coalesce(House.image_urls[1], "").label("image_url"),  # First image URL
            House.owner_id,
            House.is_approved,
            House.availability,
            House.created_at,
            House.updated_at,
            func.count(Like.id).label("like_count"),
            func.count(Review.id).label("review_count"),
            func.json_agg(
                func.json_build_object(
                    "reviewerId", Review.user_id,
                    "reviewerName", Reviewer.username,  # Use Reviewer alias
                    "rating", Review.rating,
                    "comment", Review.comment
                )
            ).label("reviews"),
            func.json_build_object(
                "id", User.id,
                "username", User.username,
                "full_name", User.full_name,
                "email", User.email,
                "contact_number", User.contact_number,
                "location", User.location,
                "profile_image", User.profile_image,
                "role", User.role,
                "is_verified", User.is_verified,
                "verification_status", User.verification_status,
                "phone_number", User.phone_number,
                "created_at", User.created_at,
                "updated_at", User.updated_at
            ).label("owner"),
        )
        .join(House, Cart.house_id == House.id)
        .join(User, User.id == House.owner_id)  # Join for house owner details
        .outerjoin(Review, Review.house_id == House.id)  # Join for reviews
        .outerjoin(Reviewer, Reviewer.id == Review.user_id)  # Alias for reviewer details
        .outerjoin(Like, Like.house_id == House.id)
        .filter(Cart.user_id == current_user.id)
        .group_by(
            Cart.id,
            House.id,
            User.id,
            Cart.added_at,
            House.title,
            House.description,
            House.price,
            House.location,
            House.room_count,
            House.amenities,
            House.image_urls,
            House.is_approved,
            House.availability,
            House.created_at,
            House.updated_at,
        )
    )

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (House.title.ilike(search_term)) | (House.description.ilike(search_term))
        )

    cart_items = query.all()

    if not cart_items:
        return []

    return [
        {
            "id": item.house_id,
            "title": item.title,
            "price": item.price,
            "location": item.location,
            "bedrooms": item.room_count,
            "room_count": item.room_count,
            "bathrooms": 0,
            "amenities": item.amenities,
            "imageUrl": item.image_url,  # First image URL
            "image_urls": item.image_urls,
            "owner_id": item.owner_id,
            "likeCount": item.like_count,
            "room_count": item.room_count,
            "userId": current_user.id,  # Current user ID
            "owner": item.owner,  # Owner details
            "reviews": item.reviews,
            'added_at':item.added_at,  # Structured reviews
        }
        for item in cart_items
    ]


@router.post("/cart/add", response_model=CartResponse)
def add_to_cart(
    cart_item: CartAdd,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    print(cart_item)
    # Check if house is already in cart
    existing_cart_item = db.query(Cart).filter(
        Cart.user_id == current_user.id,
        Cart.house_id == cart_item.house_id,
    ).first()

    if existing_cart_item:
        raise HTTPException(status_code=400, detail="House is already in the cart.")

    # Add to cart
    new_cart_item = Cart(
        user_id=current_user.id,
        house_id=cart_item.house_id,
        added_at=datetime.now(),
    )
    db.add(new_cart_item)
    db.commit()
    db.refresh(new_cart_item)

    return new_cart_item


@router.delete("/cart/remove/{house_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_from_cart(
    house_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Check if the house exists in the user's cart
    cart_item = db.query(Cart).filter(
        Cart.user_id == current_user.id,
        Cart.house_id == house_id,
    ).first()

    if not cart_item:
        raise HTTPException(status_code=404, detail="House not found in cart.")

    # Remove from cart
    db.delete(cart_item)
    db.commit()

    return {"message": "House removed from cart."}


from fastapi import HTTPException, status

@router.post("/book")
async def book_house(
    booking_data: BookingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Fetch house
    print('Booking Data:', booking_data)
    house = db.query(House).filter(House.id == booking_data.house_id).first()

    # Check if the house exists
    if not house:
        raise HTTPException(status_code=404, detail="House not found.")

    # Check if the room count is valid
    if booking_data.room_count <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Number of rooms must be greater than zero."
        )

    # Check if remaining rooms are sufficient
    # if house.remaining_rooms is None or house.remaining_rooms < booking_data.room_count:
    #     raise HTTPException(
    #         status_code=status.HTTP_400_BAD_REQUEST,
    #         detail="Not enough remaining rooms in the house."
    #     )

    # Check for overlapping bookings
    overlapping_booking = db.query(Booking).filter(
        Booking.house_id == booking_data.house_id,
        Booking.end_date > booking_data.start_date,
        Booking.start_date < booking_data.end_date,
        Booking.user_id==current_user.id,
        Booking.status != models.BookingStatus.CANCELED,
    ).first()

    if overlapping_booking:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="House is already booked for the selected dates."
        )

    # Ensure the booking duration is valid
    total_days = (booking_data.end_date - booking_data.start_date).days
    if total_days <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End date must be after the start date."
        )

    # Convert price to integer
    def clean_price(price: str) -> int:
        """
        Converts a price string with commas or dots into an integer.
        If the price does not contain commas or dots, it returns the price as an integer.
        Example: "2,500.50" -> 250050
        Example: "2500" -> 2500
        """
        if "," in price or "." in price:
            cleaned_price = price.replace(",", "").replace(".", "")
            return int(cleaned_price)
        return int(price)

    price = house.price

    # Calculate total price based on booking type
    if booking_data.booking_type == "monthly":
        # Calculate the number of full months
        full_months = (booking_data.end_date.year - booking_data.start_date.year) * 12 + (booking_data.end_date.month - booking_data.start_date.month)
        if booking_data.end_date.day > booking_data.start_date.day:
            full_months += 1

        # Validate that the booking duration aligns with full months
        if (booking_data.end_date - booking_data.start_date).days < 28:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Monthly bookings must be for at least one full month."
            )

        total_price = full_months * price * booking_data.room_count
    else:
        # Daily booking
        total_price = total_days * price * booking_data.room_count

    # Create new booking
    new_booking = Booking(
        house_id=booking_data.house_id,
        user_id=current_user.id,
        start_date=booking_data.start_date,
        end_date=booking_data.end_date,
        total_price=total_price,
        room_count=booking_data.room_count,
        guest_count=booking_data.guest_count,
        special_request=booking_data.special_request,
        status=models.BookingStatus.PENDING,
        booking_type=booking_data.booking_type,
    )
    db.add(new_booking)
    
    try:
    # Send email to house owner
                send_booking_email_to_owner(
                    to_email=house.owner.email,
                    subject="New Booking Request",
                    template_name="owner_booking.html",
                    house=house.title,
                    currency=house.currency,
                    booking_type=new_booking.booking_type,
                    username=current_user.username,
                    end_date=new_booking.end_date,
                    start_date=new_booking.start_date,
                    
                )

                # Send email to user
                send_booking_email_to_booker(
                    to_email=current_user.email,
                    subject="Booking Request Submitted",
                    house=house.title,
                    template_name="user_req.html",
                    username=current_user.username,
                    start_date=new_booking.start_date,
                    end_date=new_booking.end_date,
                    currency=house.currency,
                    booking_type=new_booking.booking_type,
                    total_price=total_price,
                    room_no=new_booking.room_count
                )
                db.commit()
                db.refresh(new_booking)

    except Exception as e:
        print(e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail='Failed to send email')

   
     
    return new_booking




# @router.get("/user/bookings", response_model=List[schemas.BookingResponse])
@router.get("/user/bookings",response_model=List[schemas.BookingResponse])
def get_user_bookings(
    search: str = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),  # Ensure the user is logged in
):
    # Query user bookings and join with related house details
    query = db.query(models.Booking).join(models.House).filter(
        models.Booking.user_id == current_user.id
    )
    
    if search:
        query = query.filter(
            models.House.title.ilike(f"%{search}%") | 
            models.House.description.ilike(f"%{search}%")
        )

    bookings = query.all()
    
    # Return the bookings with associated house details
    print(bookings)
    return bookings
@router.get("/bookings/{booking_id}",response_model=schemas.BookingResponse)
def get_user_bookings(
    booking_id: int,
    search: str = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),  # Ensure the user is logged in
):
    print(booking_id)
    if not current_user:
        return HTTPException(status_code=401, detail="You must be logged in to view bookings")
    try:
    # Query user bookings and join with related house details
            query = db.query(models.Booking).join(models.House).filter(
                models.Booking.user_id == current_user.id,
                models.Booking.id == booking_id
            )
            
        

            booking = query.first()
            print(booking)
            if not booking:
                    raise HTTPException(status_code=404, detail="Booking not found")
            
            print(booking)
            # Return the bookings with associated house details
            return booking
    except Exception as e:
      
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail="An error Occured Please try again later")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from sqlalchemy.orm import joinedload

@router.get("/user/house-bookings", response_model=List[schemas.BookingResponse])
def get_user_house_bookings(
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),  # Ensure the user is logged in
):
    if not current_user:
        raise HTTPException(status_code=401, detail="You must be logged in to view bookings")

    try:
        # Query all bookings made by other users to the current user's houses
        query = db.query(models.Booking).join(models.House).filter(
            models.House.owner_id == current_user.id,  # Filter by houses owned by the current user
            models.Booking.user_id != current_user.id  # Exclude bookings made by the current user
        ).join(models.User, models.User.id == models.Booking.user_id)  # Join the User model for the booking owner

        # Optional search filter
        if search:
            query = query.filter(models.House.title.ilike(f"%{search}%"))  # Ensure `name` column exists in House model

        bookings = query.all()

        if not bookings:
            raise HTTPException(status_code=404, detail="No bookings found for your houses")

        return bookings

    except HTTPException as he:
        # Re-raise HTTPException to return specific error messages
        raise he

    except Exception as e:
        # Log the actual error for debugging
        logger.error(f"Error fetching bookings: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching bookings. Please try again later."
        )




# @router.post("/cancel/{booking_id}", response_model=BookingResponse)
@router.post("/booking/cancel/{booking_id}",status_code=status.HTTP_200_OK)
def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Retrieve booking
    booking = db.query(Booking).filter(
        Booking.id == booking_id,
        Booking.user_id == current_user.id,
    ).first()

    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found.")
    print(booking)
    # Cancel booking
    
    booking.status = models.BookingStatus.CANCELED
    db.commit()

    # Notify owner
    house = db.query(House).filter(House.id == booking.house_id).first()
    owner_email = house.owner.email
    owner_username=house.owner.full_name or house.owner.username
    house_title=house.title,
    user_email=booking.user.email 
    booking_start=booking.start_date
    booking_end=booking.end_date
    rooms_no=booking.room_count
    user_username=current_user.full_name or current_user.username



    notification_data = [
        {
            "to_email": user_email,
            "username": user_username,
            "subject": "Booking Cancellation",
            "template_name": "booking_cancellation_by_owner.html",
            "house_title":house_title,
            "rooms_no": rooms_no,
            "end_date": booking_end,  # Use booking's end_date
            "start_date": booking_start,  # Use booking's start_date
        },
        {
            "to_email": owner_email,
            "username":owner_username,
            "subject": "Booking Cancellation",
            "template_name": "booking_cancellation.html",
            "house_title": house_title,
            "rooms_no": rooms_no,
            "guest_name": user_username,  # Guest is the booking user
            "end_date": booking_end,  # Use booking's end_date
            "start_date": booking_start,  # Use booking's start_date
        },
    ]

    for data in notification_data:
        send_booking_cancellation_email(
            to_email=data["to_email"],
            username=data["username"],
            subject=data["subject"],
            template_name=data["template_name"],
            house_title=data["house_title"],
            rooms_no=data.get("rooms_no"),  # Pass rooms_no if available
            guest_name=data.get("guest_name"),  # Pass guest_name if available
            start_date=data.get("start_date"),  # Pass start_date if available
            end_date=data.get("end_date"),  # Pass end_date if available
        )


    return booking


@router.post("/booking/house_owner/cancel/{booking_id}",status_code=status.HTTP_200_OK)
def owner_cancel_booking(
    booking_id: int,

    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    

    booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found.")

    if booking.status == models.BookingStatus.CANCELED :
        raise HTTPException(
            status_code=400, detail="Only pending or approved bookings can be Canceled."
        )

    if booking.house.owner_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="You are not authorized to approve this booking."
        )
    
    booking.status = models.BookingStatus.CANCELED
    db.commit()

    # Notify owner
    house = db.query(House).filter(House.id == booking.house_id).first()
    owner_email = house.owner.email
    owner_username=house.owner.full_name or house.owner.username
    house_title=house.title,
    user_email=booking.user.email 
    booking_start=booking.start_date
    booking_end=booking.end_date
    rooms_no=booking.room_count
    user_username=current_user.full_name or current_user.username



    notification_data = [
        {
            "to_email": user_email,
            "username": user_username,
            "subject": "Booking Cancellation",
            "template_name": "booking_cancellation_by_house_owner.html",
            "house_title":house_title,
            "rooms_no": rooms_no,
            "end_date": booking_end,  # Use booking's end_date
            "start_date": booking_start,  # Use booking's start_date
        },
        {
            "to_email": owner_email,
            "username":owner_username,
            "subject": "Booking Cancellation",
            "template_name": "booking_user_notification_cancelled_by_owner.html",
            "house_title": house_title,
            "rooms_no": rooms_no,
            "guest_name": user_username,  # Guest is the booking user
            "end_date": booking_end,  # Use booking's end_date
            "start_date": booking_start,  # Use booking's start_date
        },
    ]

    for data in notification_data:
        send_booking_cancellation_email(
            to_email=data["to_email"],
            username=data["username"],
            subject=data["subject"],
            template_name=data["template_name"],
            house_title=data["house_title"],
            rooms_no=data.get("rooms_no"),  # Pass rooms_no if available
            guest_name=data.get("guest_name"),  # Pass guest_name if available
            start_date=data.get("start_date"),  # Pass start_date if available
            end_date=data.get("end_date"),  # Pass end_date if available
        )


    return booking



client=AsyncQStash(base_url=QSTASH_URL,token=QSTASH_TOKEN)


@router.post("/bookings/{booking_id}/approve", status_code=status.HTTP_200_OK, response_model=None)
async def approve_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Approve a booking and trigger the reminder workflow using QStash.
    """
    # Retrieve booking
    booking = db.query(Booking).filter(Booking.id == booking_id).first()

    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found.")

    if booking.status not in ["pending", "approved"]:
        raise HTTPException(status_code=400, detail="Only pending bookings can be approved.")

    if booking.house.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="You are not authorized to approve this booking.")

    # Approve booking
    booking.status = "approved"
    
    # Send approval emails
    notification_data = [
        {
            "to_email": booking.user.email,
            "username": booking.user.full_name or booking.user.username,
            "subject": "Booking Approved",
            "template_name": "send_booking_email.html",
            "house_title": booking.house.title,
            "rooms_no": booking.room_count,
            "end_date": booking.end_date,
            "start_date": booking.start_date,
        },
        {
            "to_email": booking.house.owner.email,
            "username": booking.house.owner.full_name or booking.house.owner.username,
            "subject": "Booking Approved for Your Property",
            "template_name": "booking_owner_email.html",
            "house_title": booking.house.title,
            "rooms_no": booking.room_count,
            "guest_name": booking.user.full_name or booking.user.username,
            "end_date": booking.end_date,
            "start_date": booking.start_date,
        },
    ]

    # for data in notification_data:
    #     send_booking_approved_email(**data)

    # db.commit()

    # 🚀 **Trigger Reminder Workflow via QStash**
    current_date = datetime.now().date()
    booking_start_date = booking.start_date.date()

    # **Ensure reminders are only sent if the booking date is in the future**
    if booking_start_date > current_date:
         await call_trigger_reminders()
    return booking





WEBSITE_URL = "https://angelhouslistingwebsite.vercel.app"
TERMS_URL = f"{WEBSITE_URL}/terms"
PRIVACY_URL = f"{WEBSITE_URL}/privacy&policy"

@router.post("/submit-appeal")
async def submit_appeal(
    data: schemas.AppealRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    try:
        if not current_user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        if current_user.email != data.email:
            raise HTTPException(status_code=400, detail="Email mismatch")

        if not data.message.strip():
            raise HTTPException(status_code=400, detail="Empty message")

        # Database operations
        try:
            booking = db.query(models.Booking).filter(models.Booking.id == data.bookingId).first()
            house = db.query(models.House).filter(models.House.id == data.house_id).first()
            house_owner = db.query(models.User).filter(models.User.id == house.owner_id).first()
        except SQLAlchemyError as e:
            logger.error(f"Database error: {str(e)}")
            raise HTTPException(status_code=500, detail="Database operation failed")

        if not booking:
            raise HTTPException(status_code=400, detail="Booking not found")
        if not house:
            raise HTTPException(status_code=400, detail="House not found")

        # Email sending with error handling
        email_success = True
        try:
            # Email to Booking Owner
            send_email(
                to_email=data.email,
                subject='Your Appeal Has Been Received 🏠✨',
                template_name='send_book_appeal_to_booking_owner.html',
                template_vars={
                    "name": data.name,
                    "message": data.message,
                    "house_title": house.title,
                    "booking_id": booking.id,
                    "website_url": WEBSITE_URL,
                    "terms_url": TERMS_URL,
                    "privacy_url": PRIVACY_URL
                }
            )
        except Exception as e:
            logger.error(f"Failed to send confirmation email: {str(e)}")
            email_success = False

        try:
            # Email to House Owner
            send_email(
                to_email=house_owner.email,
                subject='New Appeal Alert for Your Listing 🚨',
                template_name='send_book_appeal_to_house_owner.html',
                template_vars={
                    "owner_name": house_owner.first_name,
                    "tenant_name": data.name,
                    "message": data.message,
                    "house_title": house.title,
                    "booking_id": booking.id,
                    "website_url": WEBSITE_URL,
                    "terms_url": TERMS_URL,
                    "privacy_url": PRIVACY_URL
                }
            )
        except Exception as e:
            logger.error(f"Failed to send house owner notification: {str(e)}")
            email_success = False

        if not email_success:
            raise HTTPException(status_code=500, detail="Appeal submitted but some notifications failed")

        return {"success": True, "message": "Appeal submitted successfully"}

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
