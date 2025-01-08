from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import Base, get_db
import pytest
from app.models import User
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
def test_user():
    user = {
        "username": "testuser",
        "full_name": "Test User",
        "email": "test@example.com",
        "password": "testpassword",
        "contact_number": "1234567890",
        "location": "Test Location"
    }
    return user

def test_create_user(test_user):
    response = client.post("/register", json=test_user)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == test_user["email"]
    assert data["username"] == test_user["username"]
    assert "password" not in data

def test_login_user(test_user):
    # First create a user
    client.post("/register", json=test_user)
    
    # Try to login
    login_data = {
        "email": test_user["email"],
        "password": test_user["password"]
    }
    response = client.post("/login", json=login_data)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_login_wrong_password(test_user):
    # First create a user
    client.post("/register", json=test_user)
    
    # Try to login with wrong password
    login_data = {
        "email": test_user["email"],
        "password": "wrongpassword"
    }
    response = client.post("/login", json=login_data)
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid credentials"

def test_get_current_user(test_user):
    # First create and login user
    client.post("/register", json=test_user)
    login_response = client.post("/login", json={
        "email": test_user["email"],
        "password": test_user["password"]
    })
    token = login_response.json()["access_token"]
    
    # Get current user
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/me", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == test_user["email"]
    assert data["username"] == test_user["username"]

def test_get_current_user_invalid_token():
    headers = {"Authorization": "Bearer invalid_token"}
    response = client.get("/me", headers=headers)
    assert response.status_code == 401
