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


from typing import Optional, List, Union
from enum import Enum
from pydantic import BaseModel, Field,  EmailStr
from fastapi import Form, UploadFile, File, Depends
from datetime import datetime


class HouseCreateUpdated(BaseModel):
    title: str = Field(..., description="The title of the house listing", min_length=5, max_length=100)
    description: str = Field(..., description="A brief description of the house", min_length=3)
    price: str = Field(..., description="The price of the house")
    deposit: str = Field(..., description="The refundable deposit of the house")
    location: str = Field(..., description="The location of the house", min_length=3)
    room_count: int = Field(..., description="The number of rooms in the house", gt=0)
    transaction_id: str = Field(..., description="Transaction id for the house")
    currency: str = Field("Kes", description="Type of currency (default: Kes)")
    facebook: Optional[str] = Field(None, description="Facebook link")
    whatsapp: Optional[str] = Field(None, description="WhatsApp link")
    linkedin: Optional[str] = Field(None, description="LinkedIn link")
    country: Optional[str] = Field(None, description="Country where the house is situated")
    phone_number: Optional[str] = Field(None, description="House contact number")
    email: Optional[EmailStr] = Field(None, description="House contact email")
    type: HouseType = Field(..., description="The type of house (e.g., apartment, villa)")
    amenities: str = Field(..., description="Comma-separated list of amenities (e.g., Wi-Fi, parking)")
    availability: bool = Field(True, description="Whether the house is available for rent/sale")
    
    # Additional optional fields that might be useful
    bedrooms: Optional[int] = Field(None, description="Number of bedrooms", gt=0)
    bathrooms: Optional[int] = Field(None, description="Number of bathrooms", gt=0)
    square_footage: Optional[int] = Field(None, description="Size of the house in square feet", gt=0)
    year_built: Optional[int] = Field(None, description="Year the house was built")
    parking_spots: Optional[int] = Field(None, description="Number of parking spots", ge=0)
    pet_friendly: Optional[bool] = Field(None, description="Whether the house is pet-friendly")
    furnished: Optional[bool] = Field(None, description="Whether the house is furnished")
    sale_type: Optional[str] = Field(None, description="Type of sale (e.g., rent, sale, lease)")
    
    @field_validator('email')
    def validate_email(cls, v):
        if v is not None and not v:
            return None
        return v
    
    @field_validator('phone_number')
    def validate_phone(cls, v):
        if v is not None:
            # Remove any non-digit characters for validation
            digits_only = ''.join(filter(str.isdigit, v))
            if len(digits_only) < 8:  # Assuming minimum phone length
                raise ValueError('Phone number must have at least 8 digits')
        return v
    
    @field_validator('amenities')
    def validate_amenities(cls, v):
        if not v.strip():
            raise ValueError('Amenities list cannot be empty')
        return v
    
    @classmethod
    def as_form(
        cls,
        title: str = Form(..., description="The title of the house listing"),
        description: str = Form(..., description="A brief description of the house"),
        price: str = Form(..., description="The price of the house"),
        location: str = Form(..., description="The location of the house"),
        deposit: str = Form(..., description="The refundable deposit of the house"),
        room_count: int = Form(..., description="The number of rooms in the house"),
        transaction_id: str = Form(..., description="Transaction id for the house"),
        currency: str = Form("Kes", description="Type of currency (default: Kes)"),
        facebook: Optional[str] = Form(None, description="Facebook link"),
        whatsapp: Optional[str] = Form(None, description="WhatsApp link"),
        linkedin: Optional[str] = Form(None, description="LinkedIn link"),
        country: Optional[str] = Form(None, description="Country where the house is situated"),
        phone_number: Optional[str] = Form(None, description="House contact number"),
        email: Optional[str] = Form(None, description="House contact email"),
        type: HouseType = Form(..., description="The type of house"),
        amenities: str = Form(..., description="Comma-separated list of amenities"),
        availability: bool = Form(True, description="Whether the house is available"),
        bedrooms: Optional[int] = Form(None, description="Number of bedrooms"),
        bathrooms: Optional[int] = Form(None, description="Number of bathrooms"),
        square_footage: Optional[int] = Form(None, description="Size in square feet"),
        year_built: Optional[int] = Form(None, description="Year the house was built"),
        parking_spots: Optional[int] = Form(None, description="Number of parking spots"),
        pet_friendly: Optional[bool] = Form(None, description="Whether pet-friendly"),
        furnished: Optional[bool] = Form(None, description="Whether furnished"),
        sale_type: Optional[str] = Form(None, description="Type of sale")
    ):
        return cls(
            title=title,
            description=description,
            price=price,
            deposit=deposit,
            location=location,
            room_count=room_count,
            transaction_id=transaction_id,
            currency=currency,
            facebook=facebook,
            whatsapp=whatsapp,
            linkedin=linkedin,
            country=country,
            phone_number=phone_number,
            email=email,
            type=type,
            amenities=amenities,
            availability=availability,
            bedrooms=bedrooms,
            bathrooms=bathrooms,
            square_footage=square_footage,
            year_built=year_built,
            parking_spots=parking_spots,
            pet_friendly=pet_friendly,
            furnished=furnished,
            sale_type=sale_type
        )
    
    class Config:
        form_attributes = True
        json_schema_extra = {
            "example": {
                "title": "Beautiful 3-Bedroom Apartment in Westlands",
                "description": "Modern apartment with spacious living area, fully equipped kitchen, and balcony with city views.",
                "price": "35000",
                "deposit": "350",
                "location": "Westlands, Nairobi",
                "room_count": 5,
                "transaction_id": "TRX123456789",
                "currency": "Kes",
                "country": "Kenya",
                "phone_number": "+254712345678",
                "email": "contact@example.com",
                "type": "apartment",
                "amenities": "Wi-Fi, Parking, Security, Swimming Pool, Gym",
                "bedrooms": 3,
                "bathrooms": 2,
                "square_footage": 1200,
                "year_built": 2020,
                "parking_spots": 1,
                "pet_friendly": True,
                "furnished": True,
                "sale_type": "rent"
            }
        }





class BillingAddress(BaseModel):
    street: str
    city: str
    state: str
    postalCode: str

class PayPalOrderCreateRequest(BaseModel):
    amount: float
    currency: str
    description: str
    name: str
    email: str
    billing_address: Optional[BillingAddress] = None

class PayPalOrderCreateResponse(BaseModel):
    status: str
    order_id: str
    approval_url: str
    transaction_id: int
    ec_token: str

class PayPalOrderCaptureRequest(BaseModel):
    order_id: str
    payer_id: str
    email: str
    payment_id: str

class PayPalOrderCaptureResponse(BaseModel):
    status: str
    capture_id: str
    transaction_id: int
    amount: float
    currency: str