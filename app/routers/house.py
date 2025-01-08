from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File,Form
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from app import models, schemas
from app.database import get_db
from app.services import oauth, file_handler
from app.utils import check_house_owner
from ..services.upload import upload_image
from typing import List
from sqlalchemy import or_

router = APIRouter(
    prefix="/houses",
    tags=["Houses"],
)

# @router.post("/", response_model=schemas.HouseResponse)
@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_house(
    title: str = Form(..., description="The title of the house listing"),
    description: str = Form(..., description="A brief description of the house"),
    price: int = Form(..., description="The price of the house"),
    location: str = Form(..., description="The location of the house"),
    room_count: int = Form(..., description="The number of rooms in the house"),
    type: schemas.HouseType = Form(..., description="The type of house (e.g., apartment, villa)"),
    amenities: str = Form(..., description="Comma-separated list of amenities (e.g., Wi-Fi, parking)"),
    images: List[UploadFile] = File(..., description="Upload image files for the house"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth.get_current_user),
):
    # if current_user.role != models.UserRole.house_owner or current_user.role != models.UserRole.admin:
    #     raise HTTPException(
    #         status_code=403,
    #         detail="Only house owners can create listings"
    #     )

    # Convert comma-separated strings to lists
    amenities_list = [amenity.strip() for amenity in amenities.split(",") if amenity.strip()]

    # Upload images to the cloud and get URLs
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

    # Save the house to the database
    new_house = models.House(
        title=title,
        description=description,
        price=price,
        location=location,
        room_count=room_count,
        type=type,
        amenities=amenities_list,
        image_urls=image_urls_list,
        owner_id=current_user.id,
    )
    db.add(new_house)
    db.commit()
    db.refresh(new_house)

    # Query house details along with likes and reviews
    house_details = (
        db.query(
            models.House,
            func.count(models.Like.id).label("like_count"),
            func.array_agg(models.Review.comment).label("reviews"),
            func.count(models.Review.id).label("review_count")
        )
        .outerjoin(models.Like, models.Like.house_id == models.House.id)
        .outerjoin(models.Review, models.Review.house_id == models.House.id)
        .filter(models.House.id == new_house.id)
        .group_by(models.House.id)
        .first()
    )

    if not house_details:
        raise HTTPException(status_code=404, detail="House details could not be retrieved")

    house, like_count, reviews, review_count = house_details

    # Return the response
    return {
        "house": {
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
            "is_approved": house.is_approved,
            "availability": house.availability,
        },
        "like_count": like_count,
        "review_count": review_count,
        "reviews": reviews,
    }


# @router.get("/", response_model=List[schemas.HouseResponse])

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

    # Apply filters based on search parameters
    if search.location:
        query = query.filter(models.House.location.ilike(f"%{search.location}%"))

    if search.min_price is not None:
        query = query.filter(models.House.price >= search.min_price)

    if search.max_price is not None:
        query = query.filter(models.House.price <= search.max_price)

    if search.house_type:
        query = query.filter(models.House.type == search.house_type)

    if search.amenities:
        query = query.filter(models.House.amenities.contains(search.amenities))

    if search.keywords:
        query = query.filter(
            or_(
                models.House.title.ilike(f"%{search.keywords}%"),
                models.House.description.ilike(f"%{search.keywords}%")
            )
        )

    # Apply pagination
    limit = max(search.limit or 20, 1)  # Ensure limit is positive
    offset = max(search.offset or 0, 0)  # Ensure offset is non-negative
    query = query.offset(offset).limit(limit)

    # Fetch results
    results = query.all()

    # Pre-fetch owners to avoid N+1 queries
    owner_ids = {house.owner_id for house, _, _, _ in results}
    owners = db.query(models.User).filter(models.User.id.in_(owner_ids)).all()
    owner_dict = {owner.id: owner for owner in owners}

    # Format results into a consistent schema
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
            "owner": owner_dict.get(house.owner_id),  # Include the full user object
            "is_approved": house.is_approved,
            "availability": house.availability,
            "ImageUrl": house.image_urls[0] if house.image_urls else None,
            "like_count": like_count,
            "review_count": review_count,
            "reviews": reviews if reviews else [],
        }
        for house, like_count, reviews, review_count in results
    ]

    return {"houses": houses, "total_count": len(houses), "offset": offset, "limit": limit}



@router.get("/{house_id}", status_code=status.HTTP_200_OK)
def get_house(house_id: int, db: Session = Depends(get_db)):
    # Query the house with likes and reviews using joins
    result = (
        db.query(
            models.House,
            func.count(models.Like.id).label("like_count"),
            func.array_agg(
                func.json_build_object(
                    'id', models.Review.id,
                    'user', models.User.username,
                    'owner_id',models.Review.user_id,
                    'content', models.Review.comment,
                    'rating', models.Review.rating
                )
            ).label("reviews"),
        )
        .outerjoin(models.Like, models.Like.house_id == models.House.id)
        .outerjoin(models.Review, models.Review.house_id == models.House.id)
        .outerjoin(models.User, models.User.id == models.Review.user_id)
        .filter(models.House.id == house_id)
        .group_by(models.House.id)
        .first()
    )

    # If the house doesn't exist, raise a 404 error
    if not result:
        raise HTTPException(status_code=404, detail="House not found")

    # Destructure result
    house, like_count, reviews = result

    # Return the formatted house response with fallbacks
    return {
            "id": house.id,
            "title": house.title or "No title available",
            "location": house.location or "Location not specified",
            "price": house.price or 0,
            "description": house.description or "No description available",
            "images": house.image_urls or ["/placeholder.svg?height=400&width=600"],
            "bedrooms": house.room_count or 0,
            # "bathrooms": house.bathrooms or 0,  # Assuming `bathrooms` may be missing
            # "area": house.area or 0,
            "amenities": house.amenities or [],
            "owner": {
                "name": house.owner.username or "Unknown Owner",
                "email": house.owner.email or "No email provided",
                "phone": house.owner.phone_number or "No phone number provided",
            },
            "likeCount": like_count or 0,
            "comments": reviews or [],
        }
        
    


@router.put("/{house_id}",status_code=status.HTTP_200_OK )
async def update_house(
    house_id: int,
    title: Optional[str] = Form(None, description="The updated title of the house listing"),
    description: Optional[str] = Form(None, description="The updated description of the house"),
    price: Optional[int] = Form(None, description="The updated price of the house"),
    location: Optional[str] = Form(None, description="The updated location of the house"),
    room_count: Optional[int] = Form(None, description="The updated number of rooms in the house"),
    type: Optional[schemas.HouseType] = Form(None, description="The updated type of the house"),
    amenities: Optional[str] = Form(None, description="Comma-separated updated list of amenities"),
    new_images: Optional[List[UploadFile]] = File(None, description="Upload new image files for the house"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth.get_current_user),
):
    # Check if the house belongs to the current user
    db_house = check_house_owner(db, house_id, current_user.id)

    # Update basic fields if provided
    if title:
        db_house.title = title
    if description:
        db_house.description = description
    if price is not None:
        db_house.price = price
    if location:
        db_house.location = location
    if room_count is not None:
        db_house.room_count = room_count
    if type:
        db_house.type = type

    # Convert amenities to list if provided
    if amenities:
        db_house.amenities = [amenity.strip() for amenity in amenities.split(",") if amenity.strip()]

    # Handle new image uploads
    if new_images:
        new_image_urls = []
        for image in new_images:
            try:
                # Use async function to upload the image and get the URL
                image_url = await upload_image(image)
                new_image_urls.append(image_url)
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to upload image: {image.filename}. Error: {str(e)}"
                )

        # Add new image URLs to the existing ones (extend them)
        if db_house.image_urls:
            db_house.image_urls.extend(new_image_urls)  # Extend the existing list of URLs
        else:
            db_house.image_urls = new_image_urls  # Initialize the list if it's empty

    # Commit changes to the database
    db.commit()
    db.refresh(db_house)
    return db_house

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


# @router.get("/get/user/houses")
# def get_user_houses(
#     db: Session = Depends(get_db),
#     current_user: models.User = Depends(oauth.get_current_user),
    
# ):
#     """
#     Retrieve all houses belonging to the logged-in user.
#     """
#     print(current_user)
#     if not current_user:
#         raise HTTPException(status_code=401, detail="Unauthorized user")
    
#     try:
#         houses = db.query(models.House).filter(models.House.owner_id == current_user.id).all()
#         if not houses:
#             return {"message": "No houses found for the user."}
#         return houses
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@router.get("/get/user/houses", status_code=status.HTTP_200_OK)
def get_user_houses(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth.get_current_user),
):
    """
    Retrieve all houses belonging to the logged-in user with aggregated likes and reviews.
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

        # Check if the user has houses
        if not results:
            return {"message": "No houses found for the user."}

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
                "updated_at": house.updated_at,
                "owner_id": house.owner_id,
                "is_approved": house.is_approved,
                "availability": house.availability,
                "ImageUrl": house.image_urls[0] if house.image_urls else None,
                "like_count": like_count,
                "review_count": review_count,
                "reviews": reviews if reviews else [],
            }
            for house, like_count, reviews, review_count in results
        ]

        # Return structured response
        return houses

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")