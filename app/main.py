from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from app.database import engine
from app.routers import auth, social_auth, house, reviews, admin,tokens,booking
import os
from . import models
from fastapi.middleware.cors import CORSMiddleware
from .config import SECRET_KEY
# models.Base.metadata.create_all(bind=engine)
app = FastAPI()

# Add SessionMiddleware
# Replace 'your-secret-key' with a strong secret key or use an environment variable
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace "*" with a list of allowed origins in production
    allow_credentials=True,
    allow_methods=["*"],  # Allows all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)


# Include routers

@app.get("/", tags=["Welcome"])
def read_root():
    return {"message": "Welcome to the House Listing API"}

app.include_router(auth.router)
app.include_router(social_auth.router)
app.include_router(house.router)
app.include_router(booking.router)
app.include_router(reviews.router)
app.include_router(admin.router)
app.include_router(tokens.router)
