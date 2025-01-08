from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import Base, get_db
import pytest
from app.models import User, House, UserRole

# Test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def user_token():
    # Create a regular user
    user_data = {
        "username": "testuser",
        "full_name": "Test User",
        "email": "user@example.com",
        "password": "password",
        "contact_number": "1234567890",
        "location": "Test Location"
    }
    client.post("/register", json=user_data)
    
    # Login and get token
    login_response = client.post("/login", json={
        "email": user_data["email"],
        "password": user_data["password"]
    })
    return login_response.json()["access_token"]

@pytest.fixture
def house_with_owner():
    # Create house owner
    owner_data = {
        "username": "owner",
        "full_name": "House Owner",
        "email": "owner@example.com",
        "password": "password",
        "contact_number": "1234567890",
        "location": "Test Location"
    }
    client.post("/register", json=owner_data)
    
    # Set as house owner
    db = TestingSessionLocal()
    owner = db.query(User).filter(User.email == owner_data["email"]).first()
    owner.role = UserRole.house_owner
    db.commit()
    
    # Login owner
    login_response = client.post("/login", json={
        "email": owner_data["email"],
        "password": owner_data["password"]
    })
    owner_token = login_response.json()["access_token"]
    
    # Create house
    house_data = {
        "title": "Test House",
        "description": "A beautiful test house",
        "price": 1000,
        "location": "Test Location",
        "room_count": 3,
        "type": "one_bedroom",
        "amenities": ["wifi", "parking"],
        "image_urls": ["image1.jpg", "image2.jpg"]
    }
    
    headers = {"Authorization": f"Bearer {owner_token}"}
    response = client.post("/houses/", json=house_data, headers=headers)
    return response.json()["id"]

def test_create_review(user_token, house_with_owner):
    review_data = {
        "rating": 5,
        "comment": "Great house!",
        "house_id": house_with_owner
    }
    
    headers = {"Authorization": f"Bearer {user_token}"}
    response = client.post("/reviews/", json=review_data, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["rating"] == review_data["rating"]
    assert data["comment"] == review_data["comment"]

def test_get_house_reviews(user_token, house_with_owner):
    # Create a review first
    review_data = {
        "rating": 4,
        "comment": "Nice house!",
        "house_id": house_with_owner
    }
    
    headers = {"Authorization": f"Bearer {user_token}"}
    client.post("/reviews/", json=review_data, headers=headers)
    
    # Get reviews
    response = client.get(f"/houses/{house_with_owner}/reviews")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["comment"] == review_data["comment"]

def test_update_review(user_token, house_with_owner):
    # Create a review first
    review_data = {
        "rating": 3,
        "comment": "Okay house",
        "house_id": house_with_owner
    }
    
    headers = {"Authorization": f"Bearer {user_token}"}
    create_response = client.post("/reviews/", json=review_data, headers=headers)
    review_id = create_response.json()["id"]
    
    # Update review
    update_data = {
        "rating": 5,
        "comment": "Much better than initially thought!"
    }
    
    response = client.put(f"/reviews/{review_id}", json=update_data, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["rating"] == update_data["rating"]
    assert data["comment"] == update_data["comment"]

def test_delete_review(user_token, house_with_owner):
    # Create a review first
    review_data = {
        "rating": 2,
        "comment": "Not great",
        "house_id": house_with_owner
    }
    
    headers = {"Authorization": f"Bearer {user_token}"}
    create_response = client.post("/reviews/", json=review_data, headers=headers)
    review_id = create_response.json()["id"]
    
    # Delete review
    response = client.delete(f"/reviews/{review_id}", headers=headers)
    assert response.status_code == 204
    
    # Verify review is deleted
    response = client.get(f"/houses/{house_with_owner}/reviews")
    assert response.status_code == 200
    data = response.json()
    assert not any(review["id"] == review_id for review in data)
