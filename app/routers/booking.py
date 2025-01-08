from fastapi import APIRouter, HTTPException, Depends,status
from typing import List,Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from app.database import get_db
from app import models,schemas
from app.models import Booking, Cart, House, User,Like,Review
from app.schemas import BookingCreate, CartAdd, BookingResponse, CartResponse,CartSearchResponse
from ..services.email import send_email,send_booking_email_to_owner,send_booking_email_to_booker,send_booking_approved_email,send_booking_cancellation_email  # Custom utility to send emails
from ..services.oauth import get_current_user,get_current_admin

router = APIRouter(prefix="/houses", tags=["Houses"])

@router.get("/cart", response_model=List[CartSearchResponse])
def get_cart_items(
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Fetch all houses in the current user's cart with optional search functionality.
    Includes house fields, along with like count, review count, and reviews.
    """
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
            House.type,
            House.amenities,
            House.image_urls,
            House.is_approved,
            House.availability,
            House.created_at,
            House.updated_at,
            func.count(Like.id).label("like_count"),
            func.count(Review.id).label("review_count"),
            func.array_agg(Review.comment).label("reviews"),
        )
        .join(House, Cart.house_id == House.id)
        .outerjoin(Like, Like.house_id == House.id)
        .outerjoin(Review, Review.house_id == House.id)
        .filter(Cart.user_id == current_user["id"])
        .group_by(
            Cart.id,
            House.id,
            Cart.added_at,
            House.title,
            House.description,
            House.price,
            House.location,
            House.room_count,
            House.type,
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
            "cart_id": item.cart_id,
            "house_id": item.house_id,
            "title": item.title,
            "description": item.description,
            "price": item.price,
            "location": item.location,
            "room_count": item.room_count,
            "type": item.type,
            "amenities": item.amenities,
            "image_urls": item.image_urls,
            "is_approved": item.is_approved,
            "availability": item.availability,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
            "like_count": item.like_count,
            "review_count": item.review_count,
            "reviews": item.reviews,
        }
        for item in cart_items
    ]



@router.post("/cart/add", response_model=CartResponse)
def add_to_cart(
    cart_item: CartAdd,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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


@router.delete("/cart/remove/{house_id}", response_model=CartResponse)
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


@router.post("/book", response_model=BookingResponse)
def book_house(
    booking_data: BookingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Check if house is already booked for the given dates
    overlapping_booking = db.query(Booking).filter(
        Booking.house_id == booking_data.house_id,
        Booking.end_date > booking_data.start_date,
        Booking.start_date < booking_data.end_date,
    ).first()

    if overlapping_booking:
        raise HTTPException(
            status_code=400, detail="House is already booked for the selected dates."
        )

    # Create new booking
    house = db.query(House).filter(House.id == booking_data.house_id).first()
    if not house:
        raise HTTPException(status_code=404, detail="House not found.")
    if booking_data.rooms_no == 0:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,detail="Number of rooms cannot be 0 or null")

    total_price = (booking_data.end_date - booking_data.start_date).days * house.price*booking_data.rooms_no

    new_booking = Booking(
        house_id=booking_data.house_id,
        user_id=current_user.id,
        start_date=booking_data.start_date,
        end_date=booking_data.end_date,
        total_price=total_price,
        rooms_no = booking_data.rooms_no,
        status="pending",
    )
    db.add(new_booking)
    db.commit()
    db.refresh(new_booking)

    # Send email to house owner
    owner_email = house.owner.email
    user_email = current_user.email
    house_title = house.title

    send_booking_email_to_owner(
        to_email=owner_email,
        subject="New Booking Request",
        template_name="owner_booking.html",
        house=house_title,
        username=current_user.username
    )

    # Send email to user
    send_booking_email_to_booker(
        to_email=user_email,
        subject="Booking Request Submitted",
        house=house_title,
        template_name="user_req.html",
        username=current_user.username,
        start_date=new_booking.start_date,
        end_date=new_booking.end_date,
        total_price=total_price,
        room_no = new_booking.rooms_no


    )

    return new_booking


@router.get("/user/bookings", response_model=List[schemas.BookingResponse])
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
    return bookings


@router.post("/cancel/{booking_id}", response_model=BookingResponse)
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

    # Cancel booking
    booking.status = "canceled"
    db.commit()

    # Notify owner
    house = db.query(House).filter(House.id == booking.house_id).first()
    owner_email = house.owner.email
    owner_username=house.owner.full_name or house.owner.username
    house_title=house.title,
    user_email=booking.user.email 
    booking_start=booking.start_date
    booking_end=booking.end_date
    rooms_no=booking.rooms_no
    user_username=current_user.full_name or current_user.username

    # send_email(
    #     email=owner_email,
    #     subject="Booking Cancellation",
    #     body=f"The booking for your house '{house.title}' has been canceled by {current_user.username}.",
    #     username=owner_username,
    #     house_title=house_title
        
    # )



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

@router.post("/bookings/{booking_id}/approve", response_model=schemas.BookingResponse)
def approve_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),  # Ensure the house owner is logged in
):
    # Retrieve booking
    booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()

    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found.")

    if booking.status != "pending":
        raise HTTPException(
            status_code=400, detail="Only pending bookings can be approved."
        )

    if booking.house.owner_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="You are not authorized to approve this booking."
        )

    # Approve booking
    booking.status = "approved"
    db.commit()

    # Notify both the user and the house owner
    notification_data = [
        {
            "to_email": booking.user.email,
            "username": booking.user.full_name or booking.user.username,
            "subject": "Booking Approved",
            "template_name": "send_booking_email.html",
            "house_title": booking.house.title,
            "rooms_no": booking.rooms_no,
            "end_date": booking.end_date,  # Use booking's end_date
            "start_date": booking.start_date,  # Use booking's start_date
        },
        {
            "to_email": booking.house.owner.email,
            "username": booking.house.owner.full_name or booking.house.owner.username,
            "subject": "Booking Approved for Your Property",
            "template_name": "booking_owner_email.html",
            "house_title": booking.house.title,
            "rooms_no": booking.rooms_no,
            "guest_name": booking.user.full_name or booking.user.username,  # Guest is the booking user
            "end_date": booking.end_date,  # Use booking's end_date
            "start_date": booking.start_date,  # Use booking's start_date
        },
    ]

    for data in notification_data:
        send_booking_approved_email(
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

