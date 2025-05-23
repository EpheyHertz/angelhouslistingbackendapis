import asyncio
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status, UploadFile, File,Form
from sqlalchemy.orm import Session
from sqlalchemy import Integer, cast, func,literal
from typing import List, Optional
from app import models, schemas
from app.database import get_db
from app.services import oauth, file_handler,email
from app.utils import check_house_owner
from app.services.email import send_house_notification_email
from ..services.upload import upload_image
from typing import List
from sqlalchemy import or_
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import class_mapper
from collections import defaultdict
import logging
from sqlalchemy import or_, and_, func


# Set up logging
logger = logging.getLogger("house_creation")
logging.basicConfig(level=logging.INFO)

router = APIRouter(
    prefix="/houses",
    tags=["Houses"],
)

# @router.post("/", response_model=schemas.HouseResponse)

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_house(
    background_tasks: BackgroundTasks,
    house_data: schemas.HouseCreateUpdated = Depends(schemas.HouseCreateUpdated.as_form),  # Create a Pydantic model for input validation
    images: List[UploadFile] = File(..., description="Upload image files for the house"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth.get_current_user),
):
    """Create a new house listing with images and notify admins."""
    logger.info(f"Received request to create house with title: {house_data.title}")
    
    if not current_user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authentication required")
    
    # Transaction validation
    transaction = await validate_transaction(db, house_data.transaction_id)
    
    # Upload images concurrently
    image_urls_list = await upload_images_concurrently(images)
    if not image_urls_list:
        raise HTTPException(status_code=400, detail="All image uploads failed. Please try again.")
    
    # Create house with transaction
    try:
        new_house = await create_house_in_db(db, house_data, image_urls_list, current_user.id)
        
        # Update transaction
        transaction.house_id = new_house.id
        transaction.user_id = current_user.id
        db.commit()
        
        # Send notifications asynchronously
        background_tasks.add_task(
            send_notifications,
            db=db,
            house=new_house,
            owner_id=current_user.id
        )
        
        # Return house with additional data
        return await get_house_with_stats(db, new_house.id)
    
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating house: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Helper functions
async def validate_transaction(db: Session, transaction_id: str):
    """Validate the transaction exists."""
    transaction = db.query(models.Transaction).filter(models.Transaction.transaction_id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail='Transaction not found')
    return transaction

async def upload_images_concurrently(images: List[UploadFile]) -> List[str]:
    """Upload multiple images concurrently."""
    # Create tasks for each image upload
    upload_tasks = [upload_image(image) for image in images]
    
    # Run uploads concurrently
    results = await asyncio.gather(*upload_tasks, return_exceptions=True)
    
    # Filter out exceptions and log errors
    image_urls = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Error uploading image {i}: {result}")
        else:
            image_urls.append(result)
    
    return image_urls

async def create_house_in_db(db: Session, house_data: schemas.HouseCreate, image_urls: List[str], owner_id: int) -> models.House:
    """Create a new house record in the database."""
    # Process amenities
    amenities_list = [amenity.strip() for amenity in house_data.amenities.split(",") if amenity.strip()]
    
    new_house = models.House(
        title=house_data.title,
        description=house_data.description,
        price=house_data.price,
        deposit=house_data.deposit,
        location=house_data.location,
        room_count=house_data.room_count,
        email=house_data.email,
        facebook=house_data.facebook,
        linkedin=house_data.linkedin,
        whatsapp=house_data.whatsapp,
        country=house_data.country,
        currency=house_data.currency,
        phone_number=house_data.phone_number,
        type=house_data.type,
        amenities=amenities_list,
        image_urls=image_urls,
        owner_id=owner_id,
    )
    
    db.add(new_house)
    db.commit()
    db.refresh(new_house)
    return new_house

async def send_notifications(db: Session, house: models.House, owner_id: int):
    """Send email notifications about the new house listing."""
    try:
        # Get admin emails
        admin_users = db.query(models.User).filter(models.User.role == 'admin').all()
        admin_emails = [user.email for user in admin_users]
        logger.info(f"Found {len(admin_emails)} admin emails for notification")
        
        # Get owner's email
        owner_user = db.query(models.User).filter(models.User.id == owner_id).first()
        if not owner_user:
            logger.error(f"Owner user with ID {owner_id} not found")
            return
            
        owner_email = owner_user.email
        owner_name = owner_user.username or owner_user.full_name
        logger.info(f"Preparing to send email notification to owner: {owner_email}")
        
        # Convert house to dictionary for the email
        house_dict = {
            "id": house.id,
            "title": house.title,
            "description": house.description,
            "price": house.price,
            "location": house.location,
            "room_count": house.room_count,
            "type": house.type.value if hasattr(house.type, 'value') else house.type,
            "amenities": house.amenities,
            "image_urls": house.image_urls,
            "created_at": house.created_at,
            "updated_at": house.updated_at,
            "owner_id": house.owner_id,
            "is_approved": house.is_approved,
        }
        
        email_result = await send_house_notification_email(
            admin_emails=admin_emails,
            owner_email=owner_email,
            owner_username=owner_name,
            **house_dict
        )
        
        if email_result:
            logger.info(f"Email notifications sent successfully for house ID: {house.id}")
        else:
            logger.warning(f"Email sending returned False for house ID: {house.id}")
        
    except Exception as e:
        logger.error(f"Failed to send email notification: {e}", exc_info=True)  # Include traceback
        # Don't raise exception here since this is in a background task

async def get_house_with_stats(db: Session, house_id: int) -> dict:
    """Fetch house details with likes and reviews."""
    house_details = (
        db.query(
            models.House,
            func.count(models.Like.id).label("like_count"),
            func.array_agg(models.Review.comment).label("reviews"),
            func.count(models.Review.id).label("review_count")
        )
        .outerjoin(models.Like, models.Like.house_id == models.House.id)
        .outerjoin(models.Review, models.Review.house_id == models.House.id)
        .filter(models.House.id == house_id)
        .group_by(models.House.id)
        .first()
    )
    
    if not house_details:
        raise HTTPException(status_code=404, detail="House details could not be retrieved")
    
    house, like_count, reviews, review_count = house_details
    
    return {
        "house": {
            "id": house.id,
            "title": house.title,
            "description": house.description,
            "price": house.price,
            "location": house.location,
            "room_count": house.room_count,
            "type": house.type,
            "deposit": house.deposit,
            "currency":house.currency,
            "amenities": house.amenities,
            "image_urls": house.image_urls,
            "created_at": house.created_at,
            "updated_at": house.updated_at,
            "owner_id": house.owner_id,
            "is_approved": house.is_approved,
            "availability": house.availability,
        },
        "like_count": like_count or 0,
        "review_count": review_count or 0,
        "reviews": reviews or [],
    }








@router.get("/", status_code=status.HTTP_200_OK)
def list_houses(
    search: schemas.SearchParams = Depends(),
    db: Session = Depends(get_db)
):
    """
    Fetch a list of houses with aggregated likes and reviews.
    Filters, pagination, and search criteria are applied based on user input.
    """

    # Base query with joins for likes and reviews
    query = (
        db.query(
            models.House,
            func.count(models.Like.id).label("like_count"),
            func.array_agg(models.Review.comment).label("reviews"),
            func.count(models.Review.id).label("review_count"),
        )
        .outerjoin(models.Like, models.Like.house_id == models.House.id)
        .outerjoin(models.Review, models.Review.house_id == models.House.id)
        .group_by(models.House.id)
    )

    def clean_location(location):
        """Cleans and processes the location input for better matching."""
        if not location:
            return None
        return location.strip().replace(" ", "").lower()

    try:
        # Apply filters based on search parameters
        if search.location:
            cleaned_location = clean_location(search.location)
            query = query.filter(models.House.location.ilike(f"%{cleaned_location}%"))

        if search.min_price is not None:
                query = query.filter(cast(models.House.price, Integer) >= search.min_price)

        if search.max_price is not None:
                   query = query.filter(cast(models.House.price, Integer) <= search.max_price)
        if search.house_type:
            query = query.filter(models.House.type.ilike(f"%{search.house_type}%"))

        if search.amenities:
            amenity_filters = [models.House.amenities.ilike(f"%{amenity}%") for amenity in search.amenities]
            query = query.filter(or_(*amenity_filters))

        if search.keywords:
            keyword_filter = or_(
                models.House.title.ilike(f"%{search.keywords}%"),
                models.House.description.ilike(f"%{search.keywords}%"),
                models.House.location.ilike(f"%{search.keywords}%"),
                models.House.type.ilike(f"%{search.keywords}%"),
                models.House.amenities.ilike(f"%{search.keywords}%"),
            )
            query = query.filter(keyword_filter)

        # Apply pagination
        limit = min(max(search.limit or 20, 1), 100)  # Ensures 1 ≤ limit ≤ 100
        offset = max(search.offset or 0, 0)
        query = query.offset(offset).limit(limit)

        # Fetch results
        results = query.all()

        # Pre-fetch owners to avoid N+1 queries
        owner_ids = {house.owner_id for house, _, _, _ in results}
        owners = db.query(models.User).filter(models.User.id.in_(owner_ids)).all()
        owner_dict = {
            owner.id: {
                "id": owner.id,
                "username": owner.username,
                "full_name": owner.full_name or None,
                "is_verified": owner.is_verified,
                "profile_image": owner.profile_image or None,
                "role": owner.role,
                "social_auth_provider": owner.social_auth_provider,
            }
            for owner in owners
        }

        # Format results
        houses = [
            {
                "id": house.id,
                "title": house.title,
                "description": house.description,
                "price": house.price,
                "location": house.location,
                "room_count": house.room_count,
                "type": house.type,
                "amenities": house.amenities,
                "image_urls": house.image_urls,
                "created_at": house.created_at,
                "deposit": house.deposit,
                "currency":house.currency,
                "updated_at": house.updated_at,
                "owner_id": house.owner_id,
                "owner": owner_dict.get(house.owner_id),  # Owner data
                "is_approved": house.is_approved,
                "availability": house.availability,
                "image_url": house.image_urls[0] if house.image_urls else None,
                "like_count": like_count or 0,
                "review_count": review_count or 0,
                "reviews": reviews or [],
            }
            for house, like_count, reviews, review_count in results
        ]

        return {"houses": houses, "total_count": len(houses), "offset": offset, "limit": limit}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving house listings: {str(e)}"
        )








@router.get("/house/{house_id}", status_code=status.HTTP_200_OK)
def get_house(house_id: int, db: Session = Depends(get_db)):
    # Query the house with likes (removed reviews logic)
    result = (
        db.query(
            models.House,
            func.count(models.Like.id).label("like_count"),
        )
        .outerjoin(models.Like, models.Like.house_id == models.House.id)
        .filter(models.House.id == house_id and models.House.is_approved == True)
        .group_by(models.House.id)
        .limit(1)
        .first()
    )

    # If the house doesn't exist, raise a 404 error
    if not result:
        raise HTTPException(status_code=404, detail="House not found")

    # Destructure result
    house, like_count = result

    # Return the formatted house response with fallbacks
    return {
        "id": house.id,
        "title": house.title or "No title available",
        "location": house.location or "Location not specified",
        "price": house.price or 0,
        "description": house.description or "No description available",
        "images": house.image_urls or ["/placeholder.svg?height=400&width=600"],
        "bedrooms": house.room_count or 0,
        "amenities": house.amenities or [],
        'created_at':house.created_at,
        'updated_at':house.updated_at or "No update available",
        "availability":house.availability or "No availability provided",
        "whatsapp":house.whatsapp,
        "deposit":house.deposit,
        "phone_number":house.phone_number or "No phone number provided",
        "facebook":house.facebook,
        "linkedin":house.linkedin ,
        "email":house.email or "No email provided",
        "country":house.country or "No country provided",
        "currency":house.currency or "Kes",
        "remaining_rooms":house.remaining_rooms or 0,
        "type": house.type or "No type specified",
        "owner": {
            'id': house.owner.id,
            'role': house.owner.role,
            "name": house.owner.username or "Unknown Owner",
            "email": house.owner.email or "No email provided",
            "phone": house.owner.phone_number or "No phone number provided",
            "imageUrl": house.owner.profile_image
        },
        "likeCount": like_count or 0,
        "comments": [],  # Removed reviews logic, handled by the Reviews API
    }





@router.patch("/{house_id}", status_code=status.HTTP_200_OK)
async def update_house(
    house_id: int,
    title: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    price: Optional[str] = Form(None),
    deposit: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    amenities: Optional[str] = Form(None),
    room_count: Optional[str] = Form(None),
    currency: Optional[str] = Form(None),
    type: Optional[str] = Form(None),
    images: Optional[List[UploadFile]] = File(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth.get_current_user),
):
    # print('Price',price)
    # print('New Images',images)
    # print('currency:',currency)
    # print('Current User email:',current_user.email)
    try:
        # Check house ownership
        db_house = check_house_owner(db, house_id, current_user.id)
        if not db_house:
            raise HTTPException(status_code=404, detail="House not found or permission denied.")

        # Track updates to handle no-data case
        updates_made = False

        # Update fields with validation
        if title is not None:
            db_house.title = title
            updates_made = True

        if location is not None:
            db_house.location = location
            updates_made = True

        if price is not None:
            try:
                price_val = float(price)
                if price_val <= 0:
                    raise ValueError("Price must be a positive number")
                db_house.price = price_val  # Store as string but validate as number
                updates_made = True

            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid price: {str(e)}")
        if deposit is not None:
            try:
                deposit_val = float(deposit)
                if deposit_val <= 0:
                    raise ValueError("Price must be a positive number")
                db_house.deposit = deposit_val  # Store as string but validate as number
                updates_made = True

            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid price: {str(e)}")

        if description is not None:
            db_house.description = description
            updates_made = True

        if room_count is not None:
            try:
                room_count_val = int(room_count)
                if room_count_val <= 0:
                    raise ValueError("Room count must be positive")
                db_house.room_count = room_count_val
                updates_made = True
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid room count: {str(e)}")

        if currency is not None:
            db_house.currency = currency.upper()
            updates_made = True

        if type is not None:
            db_house.type = type.lower()
            updates_made = True

        if amenities is not None:
            try:
                cleaned_amenities = [a.strip() for a in amenities.split(",") if a.strip()]
                db_house.amenities = cleaned_amenities
                updates_made = True
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid amenities format: {str(e)}")

        # Handle image uploads
        if images:
            new_urls = []
            for img in images:
                if not img.content_type.startswith('image/'):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid file type {img.content_type} for image upload"
                    )
                
                try:
                    url = await upload_image(img)
                    new_urls.append(url)
                    updates_made = True
                except Exception as e:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to upload image {img.filename}: {str(e)}"
                    )
            
            db_house.image_urls = db_house.image_urls + new_urls if db_house.image_urls else new_urls

        if not updates_made:
            raise HTTPException(status_code=400, detail="No valid fields provided for update")

        # Commit changes
        try:
            db.commit()
            db.refresh(db_house)
        except SQLAlchemyError as e:
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail="Database error occurred while saving changes"
            )

        return db_house

    except HTTPException as he:
        # Re-raise already handled exceptions
        raise he
    except Exception as e:
        # Catch-all for unexpected errors
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error occurred: {str(e)}"
        )




# @router.post("/{house_id}", status_code=status.HTTP_200_OK)
# async def update_house(
#     house_id: int,
#     title: Optional[str] = Form(None, description="The updated title of the house listing"),
#     description: Optional[str] = Form(None, description="The updated description of the house"),
#     price: Optional[int] = Form(None, description="The updated price of the house"),
#     location: Optional[str] = Form(None, description="The updated location of the house"),
#     room_count: Optional[int] = Form(None, description="The updated number of rooms in the house"),
#     room_no: Optional[int] = Form(None, description="The updated number of rooms in the house"),
#     type: Optional[schemas.HouseType] = Form(None, description="The updated type of the house"),
#     amenities: Optional[str] = Form(None, description="Comma-separated updated list of amenities"),
#     new_images: Optional[List[UploadFile]] = File(None, description="Upload new image files for the house"),
#     currency: Optional[str] = 'KES',
#     db: Session = Depends(get_db),
#     current_user: models.User = Depends(oauth.get_current_user),
# ):
#     print("Title:",title)
#     print("Price:",price)
#     print("New Images:",new_images)
#     print("Amenites",amenities)
#     print("Room_no",room_no)
#     try:
#         # Check if the house belongs to the current user
#         db_house = check_house_owner(db, house_id, current_user.id)
#         if not db_house:
#             raise HTTPException(
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 detail="House not found or you do not have permission to update this house."
#             )

#         # Update basic fields if provided
#         if title:
#             db_house.title = title
#         if description:
#             db_house.description = description
#         if price is not None:
#             db_house.price = price
#         if location:
#             db_house.location = location
#         if room_count is not None:
#             db_house.room_count = room_count
#         if room_no is not None:
#             db_house.room_count = room_no
#         if type:
#             db_house.type = type
#         if currency:
#             db_house.currency = currency

#         # Convert amenities to list if provided
#         if amenities:
#             db_house.amenities = [amenity.strip() for amenity in amenities.split(",") if amenity.strip()]

#         # Handle new image uploads
#         if new_images:
#             new_image_urls = []
#             for image in new_images:
#                 try:
#                     # Use async function to upload the image and get the URL
#                     image_url = await upload_image(image)
#                     new_image_urls.append(image_url)
#                 except Exception as e:
#                     raise HTTPException(
#                         status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#                         detail=f"Failed to upload image: {image.filename}. Error: {str(e)}"
#                     )

#             # Add new image URLs to the existing ones (extend them)
#             if db_house.image_urls:
#                 db_house.image_urls.extend(new_image_urls)  # Extend the existing list of URLs
#             else:
#                 db_house.image_urls = new_image_urls  # Initialize the list if it's empty

#         # Commit changes to the database
#         db.commit()
#         db.refresh(db_house)
#         return db_house

#     except HTTPException as http_exc:
#         # Re-raise HTTPException as it is already properly formatted
#         raise http_exc
#     except Exception as e:
#         # Handle any other unexpected errors
#         db.rollback()  # Rollback the transaction in case of an error
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"An unexpected error occurred: {str(e)}"
#         )

@router.delete("/{house_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_house(
    house_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth.get_current_user)
):
    db_house = check_house_owner(db, house_id, current_user.id)
    db.delete(db_house)
    db.commit()
    return {"detail": "House deleted"}

@router.post("/{house_id}/images")
async def upload_house_images(
    house_id: int,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth.get_current_user)
):
    db_house = check_house_owner(db, house_id, current_user.id)
    
    image_urls = []
    for file in files:
        image_url = await file_handler.save_upload_file(file, "house_images")
        image_urls.append(image_url)
    
    db_house.image_urls.extend(image_urls)
    db.commit()
    
    return {"image_urls": image_urls}

@router.post("/{house_id}/like", response_model=schemas.LikeResponse)
def like_house(
    house_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth.get_current_user)
):
    existing_like = db.query(models.Like).filter(
        models.Like.house_id == house_id,
        models.Like.user_id == current_user.id
    ).first()
    
    if existing_like:
        try:
            db.delete(existing_like)
            db.commit()
        except Exception as e:
           raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to dislike the House"
        )
    
    new_like = models.Like(house_id=house_id, user_id=current_user.id)
    db.add(new_like)
    db.commit()
    db.refresh(new_like)
    return new_like


@router.get("/get/user/houses", status_code=status.HTTP_200_OK)
def get_user_houses(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth.get_current_user),
):
    """
    Retrieve all houses belonging to the logged-in user with aggregated likes and reviews.
    Include user details in each house as the owner object.
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Unauthorized user")
    
    try:
        # Query houses owned by the user, with aggregated likes and reviews
        query = (
            db.query(
                models.House,
                func.count(models.Like.id).label("like_count"),
                func.array_agg(models.Review.comment).label("reviews"),
                func.count(models.Review.id).label("review_count"),
            )
            .outerjoin(models.Like, models.Like.house_id == models.House.id)
            .outerjoin(models.Review, models.Review.house_id == models.House.id)
            .filter(models.House.owner_id == current_user.id)
            .group_by(models.House.id)
        )

        results = query.all()

        # Format user information
        user_info = {
            "user_id": current_user.id,
            "email": current_user.email,
            "username": current_user.username,
            "profile_image": current_user.profile_image,
            "phone_number": current_user.phone_number,
            "full_name": current_user.full_name,
        }

        # Check if the user has houses
        if not results:
            return {"message": "No houses found for the user."}

        # Format house results with embedded owner details
        houses = [
            {
                "id": house.id,
                "title": house.title,
                "description": house.description,
                "price": house.price,
                "location": house.location,
                "room_count": house.room_count,
                "type": house.type,
                "amenities": house.amenities,
                "image_urls": house.image_urls,
                "created_at": house.created_at,
                "updated_at": house.updated_at,
                "owner_id": house.owner_id,
                "deposit":house.deposit,
                "currency":house.currency or 'Kes',
                "is_approved": house.is_approved,
                "availability": house.availability,
                "ImageUrl": house.image_urls[0] if house.image_urls else None,
                "like_count": like_count,
                "review_count": review_count,
                "reviews": reviews if reviews else [],
                "owner": user_info,  # Embed user details as owner
            }
            for house, like_count, reviews, review_count in results
        ]

        # Return structured response
        return houses

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")




@router.get("/{user_id}/houses", status_code=status.HTTP_200_OK)
def get_user_houses(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth.get_current_user),
):
    """
    Retrieve all houses belonging to the logged-in user with aggregated likes and reviews.
    Include user details in each house as the owner object.
    """
    # Validate user authentication
    if not current_user:
        raise HTTPException(status_code=401, detail="Please log in to view your houses.")
    
    # Ensure the user is querying their own houses
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="You are not authorized to access these houses.")

    try:
        # Query houses owned by the user
        results = (
            db.query(
                models.House,
                func.count(models.Like.id).label("like_count"),
                func.array_agg(models.Review.comment).label("reviews"),
                func.count(models.Review.id).label("review_count"),
            )
            .outerjoin(models.Like, models.Like.house_id == models.House.id)
            .outerjoin(models.Review, models.Review.house_id == models.House.id)
            .filter(models.House.owner_id == user_id)
            .group_by(models.House.id)
            .all()
        )

        # Validate if any houses are found
        if not results:
            return {"message": "No houses found for this user."}

        # User info to include as the owner of each house
        user_info = {
            "user_id": current_user.id,
            "email": current_user.email,
            "username": current_user.username,
            "profile_image": current_user.profile_image,
            "phone_number": current_user.phone_number,
            "full_name": current_user.full_name,
        }

        # Process query results
        houses = []
        for house, like_count, reviews, review_count in results:
            houses.append({
                "id": house.id,
                "title": house.title,
                "description": house.description,
                "price": house.price,
                "location": house.location,
                "room_count": house.room_count,
                "type": house.type,
                "deposit":house.deposit,
                "currency":house.currency or "Kes",
                "amenities": house.amenities,
                "image_urls": house.image_urls,
                "created_at": house.created_at,
                "updated_at": house.updated_at,
                "owner_id": house.owner_id,
                "is_approved": house.is_approved,
                "availability": house.availability,
                "ImageUrl": house.image_urls[0] if house.image_urls else None,
                "like_count": like_count or 0,
                "review_count": review_count or 0,
                "reviews": reviews or [],
                "owner": user_info,  # Include user details as the owner
            })

        # Return the processed list of houses
        return {"houses": houses}

    except Exception as e:
        # Log detailed error for debugging
        print(f"Error fetching user houses: {e}")
        raise HTTPException(status_code=500, detail="An internal server error occurred.")



router.post('/booking/send/appeal',status_code=status.HTTP_200_OK)
def send_booking_appeal(
    appeal_data: schemas.BookingAppeal,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth.get_current_user),
):
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail='You must be Authorized or logged in for this request')
    
    try:


        booking=db.query(models.Booking).first(
            models.Booking.id==appeal_data.bookingId,
            models.Booking.user_id==appeal_data.house_id
            
        )
        if not booking:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail='The Booking was Not Found')
        house=db.query(models.House).first(
            models.House.id==booking.house_id,
        )
        if not house:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail='House with the id was not found')
        house_owner=db.query(models.User).first(
            models.User.id==house.owner_id
        )
        if not house_owner:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail='House did not have an Owner')
        try:
            email.send_appeal_confirmation_email_to_booking_house_owner(
                to_email=house_owner.email,
                subject=f"An appeal to Booking By  {current_user.full_name or current_user.username}",
                template_name='send_appeal_email_owner.html'
            )
        except Exception as e:
          raise HTTPException(status_code=500,detail=f"An error occurred: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail='An error occured on our end!Please try again Later.')
