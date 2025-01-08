from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app import models, schemas
from app.database import get_db
from app.services import oauth

router = APIRouter(tags=["Reviews Api Routes"])

@router.post("/reviews/", response_model=schemas.ReviewResponse)
def create_review(
    review: schemas.ReviewCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth.get_current_user)
):
    # Check if house exists
    house = db.query(models.House).filter(models.House.id == review.house_id).first()
    if not house:
        raise HTTPException(status_code=404, detail="House not found")

    # Check if user has already reviewed this house
    existing_review = db.query(models.Review).filter(
        models.Review.house_id == review.house_id,
        models.Review.user_id == current_user.id
    ).first()
    
    if existing_review:
        raise HTTPException(
            status_code=400,
            detail="You have already reviewed this house"
        )

    # Create new review
    new_review = models.Review(**review.model_dump(), user_id=current_user.id)
    db.add(new_review)
    db.commit()
    db.refresh(new_review)
    return new_review

@router.get("/houses/{house_id}/reviews", response_model=List[schemas.ReviewResponse])
def get_house_reviews(house_id: int, db: Session = Depends(get_db)):
    # Check if house exists
    house = db.query(models.House).filter(models.House.id == house_id).first()
    if not house:
        raise HTTPException(status_code=404, detail="House not found")

    reviews = db.query(models.Review).filter(models.Review.house_id == house_id).all()
    return reviews

@router.put("/reviews/{review_id}", response_model=schemas.ReviewResponse)
def update_review(
    review_id: int,
    review_update: schemas.ReviewUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth.get_current_user)
):
    # Check if review exists and belongs to the current user
    db_review = db.query(models.Review).filter(
        models.Review.id == review_id,
        models.Review.user_id == current_user.id
    ).first()
    
    if not db_review:
        raise HTTPException(
            status_code=404,
            detail="Review not found or you don't have permission to update it"
        )

    # Update review
    for field, value in review_update.model_dump(exclude_unset=True).items():
        setattr(db_review, field, value)
    
    db.commit()
    db.refresh(db_review)
    return db_review

@router.delete("/reviews/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_review(
    review_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth.get_current_user)
):
    # Check if review exists and belongs to the current user
    db_review = db.query(models.Review).filter(
        models.Review.id == review_id,
        models.Review.user_id == current_user.id
    ).first()
    
    if not db_review:
        raise HTTPException(
            status_code=404,
            detail="Review not found or you don't have permission to delete it"
        )

    db.delete(db_review)
    db.commit()
    return {"detail": "Review deleted"}

@router.get("/users/{user_id}/reviews", response_model=List[schemas.ReviewResponse])
def get_user_reviews(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth.get_current_user)
):
    # Check if user exists
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    reviews = db.query(models.Review).filter(models.Review.user_id == user_id).all()
    return reviews
