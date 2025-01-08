from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import Base, get_db
import pytest
from app.models import User, House, UserRole
from app.utils import hash_password

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
def house_owner_token():
    # Create a house owner
    user_data = {
        "username": "houseowner",
        "full_name": "House Owner",
        "email": "owner@example.com",
        "password": "password",
        "contact_number": "1234567890",
        "location": "Test Location"
    }
    response = client.post("/register", json=user_data)
    
    # Set user role to house_owner in database
    db = TestingSessionLocal()
    user = db.query(User).filter(User.email == user_data["email"]).first()
    user.role = UserRole.house_owner
    db.commit()
    
    # Login and get token
    login_response = client.post("/login", json={
        "email": user_data["email"],
        "password": user_data["password"]
    })
    return login_response.json()["access_token"]

@pytest.fixture
def test_house():
    return {
        "title": "Test House",
        "description": "A beautiful test house",
        "price": 1000,
        "location": "Test Location",
        "room_count": 3,
        "type": "one_bedroom",
        "amenities": ["wifi", "parking"],
        "image_urls": ["image1.jpg", "image2.jpg"]
    }

def test_create_house(house_owner_token, test_house):
    headers = {"Authorization": f"Bearer {house_owner_token}"}
    response = client.post("/houses/", json=test_house, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == test_house["title"]
    assert data["price"] == test_house["price"]

def test_create_house_unauthorized():
    # Create regular user and get token
    user_data = {
        "username": "regularuser",
        "full_name": "Regular User",
        "email": "regular@example.com",
        "password": "password",
        "contact_number": "1234567890",
        "location": "Test Location"
    }
    client.post("/register", json=user_data)
    login_response = client.post("/login", json={
        "email": user_data["email"],
        "password": user_data["password"]
    })
    token = login_response.json()["access_token"]
    
    # Try to create house
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post("/houses/", json=test_house, headers=headers)
    assert response.status_code == 403

def test_get_houses(house_owner_token, test_house):
    # Create a house first
    headers = {"Authorization": f"Bearer {house_owner_token}"}
    client.post("/houses/", json=test_house, headers=headers)
    
    # Get houses
    response = client.get("/houses/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(house["title"] == test_house["title"] for house in data)

def test_search_houses(house_owner_token, test_house):
    # Create a house first
    headers = {"Authorization": f"Bearer {house_owner_token}"}
    client.post("/houses/", json=test_house, headers=headers)
    
    # Search houses
    response = client.get("/houses/?location=Test")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(house["location"] == test_house["location"] for house in data)

def test_update_house(house_owner_token, test_house):
    # Create a house first
    headers = {"Authorization": f"Bearer {house_owner_token}"}
    create_response = client.post("/houses/", json=test_house, headers=headers)
    house_id = create_response.json()["id"]
    
    # Update house
    update_data = {"price": 2000}
    response = client.put(f"/houses/{house_id}", json=update_data, headers=headers)
    assert response.status_code == 200
    assert response.json()["price"] == update_data["price"]

def test_delete_house(house_owner_token, test_house):
    # Create a house first
    headers = {"Authorization": f"Bearer {house_owner_token}"}
    create_response = client.post("/houses/", json=test_house, headers=headers)
    house_id = create_response.json()["id"]
    
    # Delete house
    response = client.delete(f"/houses/{house_id}", headers=headers)
    assert response.status_code == 204
    
    # Verify house is deleted
    get_response = client.get(f"/houses/{house_id}")
    assert get_response.status_code == 404
