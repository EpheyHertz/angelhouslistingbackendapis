from typing import List, Optional
from pydantic import BaseModel, EmailStr, conint, field_validator
from datetime import datetime
from typing_extensions import Annotated
from enum import Enum
from pydantic import BaseModel, Field
from app.models import UserRole, VerificationStatus, SocialAuthProvider, HouseType
from fastapi import File, UploadFile
from typing import Literal
# Pydantic models for request validation
class PaymentRequest(BaseModel):
    phone_number: str
    amount: int

class STKQueryRequest(BaseModel):
    checkout_request_id: str

class UserBase(BaseModel):
    username: str
    full_name: str
    email: EmailStr
    contact_number: Optional[str] = None
    profile_image: Optional[str] = None  # Retain this as string to store image URL after upload
    location: Optional[str] = None
    verification_status: VerificationStatus = VerificationStatus.pending
    role: UserRole = UserRole.regular_user
    is_verified: bool = False
    social_auth_provider: SocialAuthProvider = SocialAuthProvider.local
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    country: Optional[str] = None
    state: Optional[str] = None
    address: Optional[str] = None
    zipcode: Optional[str] = None
    phone_number: Optional[str] = None

    class Config:
        from_attributes = True

# Schema for user creation with file upload support
class UserCreate(UserBase):
    username: str
    full_name: str
    email: EmailStr
    contact_number: Optional[str] = None
    profile_image: Optional[str] = None  # Retain this as string to store image URL after upload
    location: Optional[str] = None
    verification_status: VerificationStatus = VerificationStatus.pending
    role: UserRole = UserRole.regular_user
    is_verified: bool = False
    social_auth_provider: SocialAuthProvider = SocialAuthProvider.local
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    country: Optional[str] = None
    state: Optional[str] = None
    address: Optional[str] = None
    zipcode: Optional[str] = None
    phone_number: Optional[str] = None
    password: str
    

    class Config:
        from_attributes = True
    

class UserLogin(BaseModel):
    username:str
    password:str

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    contact_number: Optional[str] = None
    location: Optional[str] = None
    profile_image: Optional[str] = None

class UserResponse(UserBase):
    id: int
    profile_image: Optional[str]
    verification_status: VerificationStatus
    role: UserRole
    is_verified: bool
    social_auth_provider: SocialAuthProvider
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

class VerificationCodeVerification(BaseModel):
    code: str
    
class ReviewBase(BaseModel):
    rating: Annotated[int, Field(strict=True, ge=1, le=6)]
    comment: str
    house_id: int


class ReviewCreate(ReviewBase):
    pass


class ReviewUpdate(BaseModel):
    rating: Optional[Annotated[int, Field(strict=True, ge=1, le=5)]] = None
    comment: Optional[str] = None


class ReviewUserResponse(BaseModel):
    id: int
    username: str
    profile_image: Optional[str] = None

    class Config:
        from_attributes = True


class ReviewResponse(BaseModel):
    id: int
    user: ReviewUserResponse
    owner_id: int
    content: str
    rating: int
    house_id: int
    created_at: datetime
    updated_at: Optional[datetime]= None

    class Config:
        from_attributes = True

class LikeBase(BaseModel):
    house_id: int


class LikeCreate(LikeBase):
    pass


class LikeResponse(LikeBase):
    id: int
    user_id: Optional[int] = 0
    created_at: datetime

    class Config:
        from_attributes = True


class HouseType(str, Enum):
    bedsitter = "bedsitter"
    single_room = "single_room"
    one_bedroom = "one_bedroom"
    two_bedroom = "two_bedroom"


class HouseBase(BaseModel):
    title: str
    description: str
    price: int
    location: str
    room_count: int
    type: HouseType
    amenities: List[str]


class HouseCreate(HouseBase):
    image_urls: List[str]


class HouseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    price: Optional[int] = None
    location: Optional[str] = None
    image_urls: Optional[List[str]] = None
    availability: Optional[bool] = None
    room_count: Optional[int] = None
    type: Optional[HouseType] = None
    amenities: Optional[List[str]] = None


class HouseResponse(HouseBase):
    id: int
    image_urls: Optional[List[str]] = []
    owner_id: int
    is_approved: bool
    availability: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
 

    @field_validator('created_at', mode="before")
    def parse_created_at(cls, value):
        if not value:
            return None
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                raise ValueError("Invalid datetime format for 'created_at'")
        return value

    @field_validator('updated_at', mode="before")
    def parse_updated_at(cls, value):
        if not value:
            return None
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                raise ValueError("Invalid datetime format for 'updated_at'")
        return value

    class Config:
        from_attributes = True

class HouseAdminResponse(BaseModel):
    id: int
    title: str
    description: str
    price: float
    location: str
    room_count: int
    type: str
    amenities: List[str]
    owner_id: int
    is_approved: bool
    availability: bool
    created_at: str
    likes: int
    reviews: List[ReviewResponse]
    images: List[str]
class Token(BaseModel):
    access_token: str
    refresh_token:str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class LogResponse(BaseModel):
    id: int
    action: str
    user_id: int
    timestamp: datetime

    class Config:
        from_attributes = True

class EmailSchema(BaseModel):
    email: EmailStr

class PasswordReset(BaseModel):
    token: str
    new_password: str

class ChangePassword(BaseModel):
    current_password: str
    new_password: str

class BulkEmailSchema(BaseModel):
    emails: List[EmailStr]
    subject: str
    template_name: str

class GoogleAuthResponse(BaseModel):
    access_token: str
    token_type: str
    username: str
    email: EmailStr

class MobileAuthParams(BaseModel):
    platform: str  # "ios" or "android"
    device_id: str
    app_version: str

class SearchParams(BaseModel):
    location: Optional[str] = None
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    house_type: Optional[HouseType] = None
    amenities: Optional[List[str]] = None
    keywords: Optional[str] = None
    limit: Optional[int] = 100  # Default limit
    offset: Optional[int] = 0  # Default offset

class EmailSchema(BaseModel):
    email:EmailStr
    class Config:
        from_attributes = True
    
    


class VerificationToken(BaseModel):
    email: EmailStr
    token: str

class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, max_length=50, description="The updated username of the user.")
    full_name: Optional[str] = Field(None, max_length=100, description="The updated full name of the user.")
    email: Optional[EmailStr] = Field(None, description="The updated email of the user.")
    contact_number: Optional[str] = Field(None, max_length=15, description="The updated contact number of the user.")
    profile_image: Optional[str] = Field(None, description="URL of the updated profile image.")
    location: Optional[str] = Field(None, max_length=255, description="The updated location of the user.")
    id_document_url: Optional[str] = Field(None, description="URL of the updated ID document.")
    
    class Config:
        from_attributes = True



class BookingBase(BaseModel):
    house_id: int
    room_count:int
    start_date: datetime
    end_date: datetime
    special_request:Optional[str] = None
    guest_count:int
    
    

class BookingAppeal(BaseModel):
    bookingId:int 
    house_id:int
    name: str
    email: str
    message:str

class BookingCreate(BookingBase):
    booking_type: Literal["daily", "monthly"]

class BookingOwner(BaseModel):
    id: int
    username: str
    email: str
    full_name: str

class BookingResponse(BookingBase):
    id: int
    user_id: int
    total_price: float
    status: str
    house:HouseResponse
    user:BookingOwner

    class Config:
        from_attributes = True
class AppealRequest(BaseModel):
    bookingId: int
    house_id: int
    name: str
    email: EmailStr
    message: str


class CartBase(BaseModel):
    house_id: int


class CartAdd(CartBase):
    """
    Schema for adding a house to the cart.
    """
    pass


class CartResponse(BaseModel):
    """
    Schema for the cart response.
    """
    id: int
    user_id: int
    house_id: int
    added_at: datetime

    class Config:
        from_attributes = True




class CartSearchResponse(BaseModel):
    """
    Schema for returning houses in the cart with full details, excluding owner_id.
    """
    cart_id: int
    house: HouseResponse
    updated_at: Optional[datetime]
    added_at: datetime

    class Config:
        from_attributes = True


class SendCodeRequest(BaseModel):
    phone_number: str

class ValidateCodeRequest(BaseModel):
    code: str
    token: str

class CodeResponse(BaseModel):
    message: str
    success: bool

class ContactRequest(BaseModel):
    name: str
    email: str
    subject: str
    message: str

class ChatRequest(BaseModel):
    message: str



class PaymentRequestStripe(BaseModel):
    amount: int = Field(..., gt=0, description="Amount in the smallest currency unit (e.g., cents for USD)")
    currency: str = Field(..., description="Currency code (e.g., 'usd', 'eur')")
    token: str = Field(..., description="Stripe token obtained from the client-side (e.g., Stripe.js)")
    name: Optional[str] = Field(None, description="Name of the user")
    city: Optional[str] = Field(None, description="City of the user")
    email:EmailStr=Field(...,description="Email entered by the user")
    


class PaymentResponseStripe(BaseModel):
    status: str = Field(..., description="Status of the payment (e.g., 'success', 'error')")
    charge_id: Optional[str] = Field(None, description="Stripe charge ID")
    transaction_id: Optional[int] = Field(None, description="Database transaction ID")
    message: Optional[str] = Field(None, description="Error message or additional information")