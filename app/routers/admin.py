from fastapi import APIRouter, Depends, HTTPException, status, Form,Query,File,UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from typing import Optional
from app import models, schemas
from app.database import get_db
from app.services import oauth
from ..services.email import send_bulk_email, send_created_house,send_cancellation_email,send_booking_approved_email, send_house_reject_email
from ..services.upload import upload_image

router = APIRouter(
    prefix="/admins",
    tags=["Admins"]
)

@router.get("/houses/", response_model=List[schemas.HouseResponse],status_code=status.HTTP_200_OK)
# @router.get("/houses/", status_code=status.HTTP_200_OK)
def list_houses_for_admin(
    title: Optional[str] = Query(None, description="Search by house title"),
    location: Optional[str] = Query(None, description="Search by house location"),
    owner_email: Optional[str] = Query(None, description="Search by owner's email"),
    min_price: Optional[float] = Query(None, description="Minimum price for house search"),
    max_price: Optional[float] = Query(None, description="Maximum price for house search"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth.get_current_user)
):
    
    if current_user.role != models.UserRole.admin:
        raise HTTPException(status_code=403, detail="Only admins can access this endpoint")

    query = db.query(models.House)
    print(current_user.email)
    # Apply filters if search parameters are provided
    if title:
        query = query.filter(models.House.title.ilike(f"%{title}%"))
    if location:
        query = query.filter(models.House.location.ilike(f"%{location}%"))
    if owner_email:
        query = query.join(models.User, models.House.owner_id == models.User.id).filter(models.User.email.ilike(f"%{owner_email}%"))
    if min_price:
        query = query.filter(models.House.price >= min_price)
    if max_price:
        query = query.filter(models.House.price <= max_price)

    houses = query.all()
    return houses
@router.get("/houses/{house_id}", response_model=List[schemas.HouseResponse],status_code=status.HTTP_200_OK)
# @router.get("/houses/", status_code=status.HTTP_200_OK)
def list_houses_for_admin(
    house_id: int,
    title: Optional[str] = Query(None, description="Search by house title"),
    location: Optional[str] = Query(None, description="Search by house location"),
    owner_email: Optional[str] = Query(None, description="Search by owner's email"),
    min_price: Optional[float] = Query(None, description="Minimum price for house search"),
    max_price: Optional[float] = Query(None, description="Maximum price for house search"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth.get_current_user)
):
    
    if current_user.role != models.UserRole.admin:
        raise HTTPException(status_code=403, detail="Only admins can access this endpoint")

    query = db.query(models.House).filter(models.House.id==house_id)
    print(current_user.email)
    # Apply filters if search parameters are provided
    if title:
        query = query.filter(models.House.title.ilike(f"%{title}%"))
    if location:
        query = query.filter(models.House.location.ilike(f"%{location}%"))
    if owner_email:
        query = query.join(models.User, models.House.owner_id == models.User.id).filter(models.User.email.ilike(f"%{owner_email}%"))
    if min_price:
        query = query.filter(models.House.price >= min_price)
    if max_price:
        query = query.filter(models.House.price <= max_price)

    houses = query.all()
    return houses
 


@router.put("/houses/{house_id}/approve", response_model=schemas.HouseResponse)
def approve_house(house_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(oauth.get_current_user)):
    if current_user.role != models.UserRole.admin:
        raise HTTPException(status_code=403, detail="Only admins can approve houses")

    house = db.query(models.House).filter(models.House.id == house_id).first()
    if not house:
        raise HTTPException(status_code=404, detail="House not found")

    house.is_approved = True
    db.commit()
    db.refresh(house)
    return house


@router.put("/houses/{house_id}/reject", response_model=schemas.HouseResponse)
def reject_house(house_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(oauth.get_current_user)):
    if current_user.role != models.UserRole.admin:
        raise HTTPException(status_code=403, detail="Only admins can reject houses")

    house = db.query(models.House).filter(models.House.id == house_id).first()
    if not house:
        raise HTTPException(status_code=404, detail="House not found")

    house.is_approved = False
    try:
        send_house_reject_email(
            to_email=house.owner.email,
            subject="House Approval Feedback",
            template_name="send_house_reject.html",
            username=house.owner.full_name or house.owner.username,
            house_title=house.title,
            house_location=house.location,
            house_description=house.description,
            status= "Disapproved"
        )
    except:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Failed to send Reject house email.")
    db.commit()
    db.refresh(house)
    return house


@router.post("/send-bulk-email", status_code=status.HTTP_200_OK)
def send_bulk_email_endpoint(
    subject: str = Form(..., description="Subject of the email"),
    template_name: Optional[str] = Form("send_bulk_emails.html", description="Template name for the email"),
    message_body: str = Form(..., description="Body content of the email"),
    call_to_action_url: Optional[str] = Form(
       " ", description="URL for the call-to-action button"
    ),
    call_to_action_text: Optional[str] = Form("Learn More", description="Text for the call-to-action button"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth.get_current_user),
):
    """
    Endpoint to send a bulk email to all registered users.
    Only accessible by admins.

    Args:
        subject (str): The subject of the email (form field).
        template_name (str): The name of the email template to use (form field).
        message_body (str): The body content of the email (form field).
        call_to_action_url (str): URL for the call-to-action button (form field, optional).
        call_to_action_text (str): Text for the call-to-action button (form field, optional).
        db (Session): The database session.
        current_user (models.User): The currently authenticated user.

    Returns:
        dict: Response with the number of emails sent.
    """
    # Check if the current user is an admin
    if current_user.role != models.UserRole.admin:
        raise HTTPException(status_code=403, detail="Only admins can send bulk emails")
    
    # Fetch all user emails and usernames from the database
    users = db.query(models.User).all()
    user_data = [(user.email, user.username.capitalize()) for user in users if user.email]
    print(user_data)
    if not user_data:
        raise HTTPException(status_code=404, detail="No users found to send emails")
    
    # Send the bulk email
    try:
        for email, username in user_data:
            # Prepare email variables
            email_variables = {
                "recipient_name": username,
                "message_body": message_body,
                "call_to_action_url": call_to_action_url,
                "call_to_action_text": call_to_action_text
            }
            # Send the email using the corrected function
            send_bulk_email(
                to_emails=[email],  
                subject=subject,
                template_name=template_name,
                **email_variables
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send emails: {str(e)}")
    
    return {"detail": f"Emails sent successfully to {len(user_data)} users"}

@router.post("/users/", response_model=schemas.UserResponse)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db), current_user: models.User = Depends(oauth.get_current_user)):
    if current_user.role != models.UserRole.admin:
        raise HTTPException(status_code=403, detail="Only admins can create users")

    new_user = models.User(**user.model_dump())
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.get("/users/", response_model=List[schemas.UserResponse])
def list_users(
    username: Optional[str] = Query(None, description="Search by username"),
    email: Optional[str] = Query(None, description="Search by email"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth.get_current_user)
):
    if current_user.role != models.UserRole.admin:
        raise HTTPException(status_code=403, detail="Only admins can access this endpoint")

    query = db.query(models.User)

    # Apply filters if search parameters are provided
    if username:
        query = query.filter(models.User.username.ilike(f"%{username}%"))
    if email:
        query = query.filter(models.User.email.ilike(f"%{email}%"))

    users = query.all()
    return users

@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(oauth.get_current_user)):
    if current_user.role != models.UserRole.admin:
        raise HTTPException(status_code=403, detail="Only admins can delete users")

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(user)
    db.commit()
    return {"detail": "User deleted"}



# @router.post("/houses/{user_id}", response_model=schemas.HouseAdminResponse, status_code=status.HTTP_201_CREATED)
@router.post("/houses/{user_id}", status_code=status.HTTP_201_CREATED)
async def add_house(
    user_id: int,
    title: str = Form(..., description="Title of the house"),
    location: str = Form(..., description="Location of the house"),
    description: Optional[str] = Form(None, description="Description of the house"),
    price: float = Form(..., description="Price of the house"),
    is_approved: Optional[bool] = Form(False, description="Approval status of the house"),
    room_count: int = Form(0, description="Number of rooms in the house"),
    type: schemas.HouseType = Form(..., description="The type of house (e.g., apartment, villa)"),
    amenities: Optional[str] = Form(None, description="Comma-separated list of amenities"),
    images: List[UploadFile] = File(..., description="Images of the house"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth.get_current_user)
):
    # Check if the current user is an admin
    if current_user.role != models.UserRole.admin:
        raise HTTPException(status_code=403, detail="Only admins can add houses")

    # Verify if the user exists
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Process amenities into a list
    amenities_list = [amenity.strip() for amenity in amenities.split(",")] if amenities else []

    # Process uploaded images
    image_urls_list = []
    for image in images:
        try:
           
            image_url = await upload_image(image)
            image_urls_list.append(image_url)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload image: {image.filename}. Error: {str(e)}"
            )

    # Create a new house record
    new_house = models.House(
        owner_id=user_id,
        title=title,
        location=location,
        description=description,
        price=price,
        is_approved=is_approved,
        room_count=room_count,
        type=type,
        amenities=amenities_list,
        image_urls=image_urls_list
    )
    db.add(new_house)
    db.commit()
    db.refresh(new_house)

    # Fetch house details with likes and reviews
    house_details = (
        db.query(
            models.House,
            func.count(models.Like.id).label("like_count"),
            func.array_agg(models.Review.comment).label("reviews")
        )
        .outerjoin(models.Like, models.Like.house_id == models.House.id)
        .outerjoin(models.Review, models.Review.house_id == models.House.id)
        .filter(models.House.id == new_house.id)
        .group_by(models.House.id)
        .first()
    )

    if not house_details:
        raise HTTPException(status_code=404, detail="House not found after creation")

    house, like_count, reviews = house_details

    # Send email notification to the user
    try:
        send_created_house(
            email=user.email,
            subject="Your Property Has Been Listed",
            template_name="property_notification.html",
            username=user.full_name or user.username,
            house_title=house.title,
            listing_date=house.created_at.strftime("%Y-%m-%d"),
            listing_status="Approved" if house.is_approved else "Not Approved",
            location=house.location
        )
    except Exception as e:
        print(f"Failed to send email notification: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to send email notification: {e}")

    return {
        "house": house,
        "like_count": like_count,
        "reviews": reviews
    }



# Update User Details
@router.put("/users/{user_id}", response_model=schemas.UserResponse, status_code=status.HTTP_200_OK)
def update_user(
    user_id: int,
    username: Optional[str] = Form(None, description="Username of the user"),
    email: Optional[str] = Form(None, description="Email of the user"),
    full_name: Optional[str] = Form(None, description="Full name of the user"),
    is_active: Optional[bool] = Form(None, description="Active status of the user"),
    role: Optional[models.UserRole] = Form(None, description="Role of the user (admin, house_owner, regular_user)"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth.get_current_user)
):
    if current_user.role != models.UserRole.admin:
        raise HTTPException(status_code=403, detail="Only admins can update users")

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update user fields if provided
    if username:
        user.username = username
    if email:
        user.email = email
    if full_name:
        user.full_name = full_name
    if is_active is not None:
        user.is_verified = is_active
    if role:
        if role not in models.UserRole.__members__.values():
            raise HTTPException(status_code=400, detail=f"Invalid role. Allowed roles are: {', '.join(models.UserRole.__members__.values())}")
        user.role = role

    db.commit()
    db.refresh(user)
    return user



@router.delete("/houses/{house_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_house(
    house_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth.get_current_user)
):
    # Ensure that the current user is an admin
    if current_user.role != models.UserRole.admin:
        raise HTTPException(status_code=403, detail="Only admins can delete houses")

    # Find the house by its ID
    house = db.query(models.House).filter(models.House.id == house_id).first()
    
    # Check if the house exists
    if not house:
        raise HTTPException(status_code=404, detail="House not found")

    # Delete the house
    db.delete(house)
    db.commit()

    return {"detail": "House deleted"}



@router.get("/bookings", response_model=List[schemas.BookingResponse])
def get_all_bookings(
    search: str = None,
    db: Session = Depends(get_db),
    current_admin = Depends(oauth.get_current_admin),  # Ensure the admin is logged in
):
    # Search bookings by house name or description
    query = db.query(models.Booking).join(models.House, models.Booking.house_id == models.House.id)
    if search:
        query = query.filter(
            models.House.title.ilike(f"%{search}%") | models.House.description.ilike(f"%{search}%")
        )

    bookings = query.all()
    return bookings


@router.post("/bookings/{booking_id}/approve", response_model=schemas.BookingResponse)
def approve_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_admin= Depends(oauth.get_current_admin),  # Ensure the admin is logged in
):
    # Retrieve booking
    booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()

    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found.")

    if booking.status != "pending":
        raise HTTPException(
            status_code=400, detail="Only pending bookings can be approved."
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
        "subject": "Booking Approved",
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

@router.delete("/bookings/search-delete", status_code=status.HTTP_204_NO_CONTENT)
def search_and_delete_bookings(
    booking_id: Optional[int] = None,
    user_email: Optional[str] = None,
    user_username: Optional[str] = None,
    owner_email: Optional[str] = None,
    db: Session = Depends(get_db),
    current_admin=Depends(oauth.get_current_admin),  # Ensure the admin is logged in
):
    # print(current_admin.role)
    if not current_admin.role == "admin":
        raise HTTPException(status_code=403, detail="You are not authorized to delete bookings.")

    # Build the query
    query = db.query(models.Booking)

    if booking_id:
        # If a booking ID is provided, filter directly by it
        query = query.filter(models.Booking.id == booking_id)
    else:
        # Join necessary models for filtering by email/username
        query = query.join(models.User, models.Booking.user_id == models.User.id).join(
            models.House, models.Booking.house_id == models.House.id
        )

        if user_email:
            query = query.filter(models.User.email == user_email)
        if user_username:
            query = query.filter(models.User.username == user_username)
        if owner_email:
            query = query.filter(models.House.owner.has(email=owner_email))

    bookings = query.all()

    if not bookings:
        raise HTTPException(status_code=404, detail="No matching bookings found.")

    # Delete all matched bookings
    for booking in bookings:
        db.delete(booking)

    db.commit()

    return {"detail": f"Successfully deleted {len(bookings)} booking(s)."}
