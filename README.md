# House Listing Platform Backend

A comprehensive FastAPI backend for a house listing platform with features like user authentication, house management, reviews, and admin functionalities.

## Features

- User Authentication and Management
  - Registration and Login
  - Email verification
  - Password reset
  - Social authentication (Google)
  - User roles (admin, house_owner, regular_user)

- House Listings
  - Create, read, update, delete house listings
  - Image upload support
  - Admin approval system
  - Search and filtering capabilities

- Reviews and Ratings
  - Users can leave reviews and ratings
  - View house reviews
  - Update and delete reviews

- Anti-Scamming Features
  - Email verification
  - Identity verification for house owners
  - Admin tools for managing fraudulent listings

## Prerequisites

- Python 3.8+
- PostgreSQL
- SMTP server access for emails

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd house_listing
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. Initialize the database:
```bash
alembic upgrade head
```

## Running the Application

1. Start the server:
```bash
uvicorn app.main:app --reload
```

2. Access the API documentation:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API Endpoints

### Authentication
- POST /register - Register a new user
- POST /login - Login user
- POST /auth/google - Google OAuth login
- POST /password-reset - Request password reset
- POST /verify-email - Verify email address

### Houses
- POST /houses/ - Create a new house listing
- GET /houses/ - List all houses (with filters)
- GET /houses/{id} - Get house details
- PUT /houses/{id} - Update house listing
- DELETE /houses/{id} - Delete house listing
- POST /houses/{id}/images - Upload house images

### Reviews
- POST /reviews/ - Create a review
- GET /houses/{id}/reviews - Get house reviews
- PUT /reviews/{id} - Update review
- DELETE /reviews/{id} - Delete review

### Admin
- GET /admin/houses/ - List all houses for admin
- PUT /admin/houses/{id}/approve - Approve house listing
- PUT /admin/houses/{id}/reject - Reject house listing
- GET /admin/users/ - List all users
- DELETE /admin/users/{id} - Delete user

## Project Structure
```
house_listing/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── routers/
│   │   ├── auth.py
│   │   ├── social_auth.py
│   │   ├── house.py
│   │   ├── reviews.py
│   │   ├── admin.py
│   ├── services/
│   │   ├── email.py
│   │   ├── file_handler.py
│   │   ├── oauth.py
│   ├── templates/
│   │   ├── email_verification.html
│   │   ├── password_reset.html
│   │   ├── house_approval.html
├── alembic/
├── tests/
├── requirements.txt
├── .env
└── README.md
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
