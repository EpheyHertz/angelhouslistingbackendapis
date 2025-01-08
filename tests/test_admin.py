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
def admin_token():
    # Create an admin user
    user_data = {
        "username": "admin",
        "full_name": "Admin User",
        "email": "admin@example.com",
        "password": "password",
        "contact_number": "1234567890",
        "location": "Admin Location"
    }
    response = client.post("/register", json=user_data)
    
    # Set user role to admin in database
    db = TestingSessionLocal()
    user = db.query(User).filter(User.email == user_data["email"]).first()
    user.role = UserRole.admin
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

def test_admin_list_houses(admin_token, test_house):
    # Create a house first (as house owner)
    house_owner_data = {
        "username": "owner",
        "full_name": "House Owner",
        "email": "owner@example.com",
        "password": "password",
        "contact_number": "1234567890",
        "location": "Test Location"
    }
    client.post("/register", json=house_owner_data)
    db = TestingSessionLocal()
    owner = db.query(User).filter(User.email == house_owner_data["email"]).first()
    owner.role = UserRole.house_owner
    db.commit()
    
    owner_login = client.post("/login", json={
        "email": house_owner_data["email"],
        "password": house_owner_data["password"]
    })
    owner_token = owner_login.json()["access_token"]
    
    # Create house
    headers = {"Authorization": f"Bearer {owner_token}"}
    client.post("/houses/", json=test_house, headers=headers)
    
    # List houses as admin
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    response = client.get("/admin/houses/", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(house["title"] == test_house["title"] for house in data)

def test_admin_approve_house(admin_token, test_house):
    # Create and get a house first
    house_owner_data = {
        "username": "owner",
        "full_name": "House Owner",
        "email": "owner@example.com",
        "password": "password",
        "contact_number": "1234567890",
        "location": "Test Location"
    }
    client.post("/register", json=house_owner_data)
    db = TestingSessionLocal()
    owner = db.query(User).filter(User.email == house_owner_data["email"]).first()
    owner.role = UserRole.house_owner
    db.commit()
    
    owner_login = client.post("/login", json={
        "email": house_owner_data["email"],
        "password": house_owner_data["password"]
    })
    owner_token = owner_login.json()["access_token"]
    
    # Create house
    headers = {"Authorization": f"Bearer {owner_token}"}
    create_response = client.post("/houses/", json=test_house, headers=headers)
    house_id = create_response.json()["id"]
    
    # Approve house as admin
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    response = client.put(f"/admin/houses/{house_id}/approve", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["is_approved"] == True

def test_admin_reject_house(admin_token, test_house):
    # Create and get a house first (similar setup as approve test)
    house_owner_data = {
        "username": "owner",
        "full_name": "House Owner",
        "email": "owner@example.com",
        "password": "password",
        "contact_number": "1234567890",
        "location": "Test Location"
    }
    client.post("/register", json=house_owner_data)
    db = TestingSessionLocal()
    owner = db.query(User).filter(User.email == house_owner_data["email"]).first()
    owner.role = UserRole.house_owner
    db.commit()
    
    owner_login = client.post("/login", json={
        "email": house_owner_data["email"],
        "password": house_owner_data["password"]
    })
    owner_token = owner_login.json()["access_token"]
    
    # Create house
    headers = {"Authorization": f"Bearer {owner_token}"}
    create_response = client.post("/houses/", json=test_house, headers=headers)
    house_id = create_response.json()["id"]
    
    # Reject house as admin
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    response = client.put(f"/admin/houses/{house_id}/reject", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["is_approved"] == False

def test_admin_send_bulk_email(admin_token):
    # Prepare bulk email data
    bulk_email_data = {
        "emails": ["test1@example.com", "test2@example.com"],
        "subject": "Test Bulk Email",
        "template_name": "email_verification.html"
    }
    
    # Send bulk email as admin
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    response = client.post("/admin/send-bulk-email", json=bulk_email_data, headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["detail"] == "Emails sent successfully"

def test_admin_create_user(admin_token):
    # Prepare user data
    user_data = {
        "username": "newuser",
        "full_name": "New User",
        "email": "newuser@example.com",
        "password": "password",
        "contact_number": "1234567890",
        "location": "New User Location"
    }
    
    # Create user as admin
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    response = client.post("/admin/users/", json=user_data, headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["email"] == user_data["email"]
    
    # Verify the user is created in the database
    db = TestingSessionLocal()
    created_user = db.query(User).filter(User.email == user_data["email"]).first()
    assert created_user is not None
    assert created_user.username == user_data["username"]

def test_admin_delete_user(admin_token):
    # Create a user to delete
    user_data = {
        "username": "todelete",
        "full_name": "User To Delete",
        "email": "delete@example.com",
        "password": "password",
        "contact_number": "1234567890",
        "location": "Test Location"
    }
    response = client.post("/register", json=user_data)
    user_id = response.json()["id"]
    
    # Delete user as admin
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    response = client.delete(f"/admin/users/{user_id}", headers=admin_headers)
    assert response.status_code == 204
