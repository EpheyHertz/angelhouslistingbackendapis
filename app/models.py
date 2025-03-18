from decimal import Decimal
from sqlalchemy import Column, Integer, String, Boolean, Enum, ForeignKey, DateTime, ARRAY, Float,DECIMAL
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.schema import ForeignKeyConstraint
from app.database import Base
import enum
from datetime import datetime,timezone,timedelta


class UserRole(str, enum.Enum):
    admin = "admin"
    house_owner = "house_owner"
    regular_user = "regular_user"


class BookingStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    CANCELED = "canceled"


class VerificationStatus(str, enum.Enum):
    pending = "Pending"
    verified = "Verified"
    rejected = "Rejected"


class SocialAuthProvider(str, enum.Enum):
    local = "local"
    google = "google"



class HouseType(str, enum.Enum):
    apartment = 'apartment',
    villa = 'villa',
    house = 'house',
    condo = 'condo',
    townhouse = 'townhouse',
    bedsitter = "bedsitter"
    single_room = "single_room"
    one_bedroom = "one_bedroom"
    two_bedroom = "two_bedroom"

# Transaction Types Enum
class TransactionType(str, enum.Enum):
    mpesa = "mpesa"
    stripe = "stripe"
    paypal = "paypal"
    bank_transfer = "bank_transfer"
    other = "other"

# House Status Enum
class HouseStatus(str, enum.Enum):
    on_sale = "on_sale"
    sold = "sold"
    booked = "booked"

class TransactionStatus(enum.Enum):  # Don't subclass str, just use enum.Enum
    PENDING = "Pending"
    COMPLETED = "Completed"
    FAILED = "Failed"

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    transaction_type = Column(Enum(TransactionType), nullable=False)
    amount = Column(Float, nullable=False)
    transaction_id = Column(String, unique=True, index=True, nullable=False)
    house_id = Column(Integer, ForeignKey('houses.id', ondelete="CASCADE"), nullable=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete="CASCADE"), nullable=True)
    description = Column(String, nullable=True)
    currency = Column(String, nullable=False)
    
    # ✅ Fix: Pass Enum Values
    status = Column(Enum(TransactionStatus), nullable=False, default=TransactionStatus.PENDING)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    house = relationship("House", back_populates="transactions")
    user = relationship("User", back_populates="transactions")


# User model
# User Model (updated with bookings relationship)
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    full_name = Column(String)
    email = Column(String, unique=True, index=True)
    contact_number = Column(String)
    password = Column(String)
    profile_image = Column(String, nullable=True)
    location = Column(String)
    id_document_url = Column(String, nullable=True)
    verification_status = Column(Enum(VerificationStatus), default=VerificationStatus.pending)
    role = Column(Enum(UserRole), default=UserRole.regular_user)
    is_verified = Column(Boolean, default=False, index=True)
    social_auth_provider = Column(Enum(SocialAuthProvider), default=SocialAuthProvider.local)
    social_auth_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    country = Column(String, nullable=True)
    state = Column(String, nullable=True)
    address = Column(String, nullable=True)
    zipcode = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)

    # Relationships
    verification_codes = relationship("VerificationCode", back_populates="user", cascade="all, delete")
    houses = relationship("House", back_populates="owner", cascade="all, delete")
    reviews = relationship("Review", back_populates="user", cascade="all, delete")
    likes = relationship("Like", back_populates="user", cascade="all, delete")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete")
    bookings = relationship("Booking", back_populates="user", cascade="all, delete")
    cart_items = relationship("Cart", back_populates="user", cascade="all, delete")
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete")





class VerificationCode(Base):
    __tablename__ = "verification_codes"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, index=True)
    expiration_date = Column(DateTime, default=datetime.now() + timedelta(minutes=15))
    user_id = Column(Integer, ForeignKey('users.id',ondelete="CASCADE"))

    user = relationship("User", back_populates="verification_codes")

    def is_expired(self):
        return datetime.now() > self.expiration_date

# House Model (updated)
class House(Base):
    __tablename__ = "houses"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(String)
    price = Column(DECIMAL, nullable=False)
    deposit= Column(DECIMAL, nullable=True, default=0)
    location = Column(String, index=True)
    image_urls = Column(ARRAY(String))
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    is_approved = Column(Boolean, default=False)
    availability = Column(Boolean, default=True)
    room_count = Column(Integer, nullable=False)
    booked_rooms = Column(Integer, default=0)  # Tracks the number of rooms booked
    remaining_rooms = Column(Integer, default=0)  # New field for remaining rooms
    type = Column(Enum(HouseType))
    amenities = Column(ARRAY(String))
    status = Column(Enum(HouseStatus), default=HouseStatus.on_sale,nullable=True)  # New field for house status
    on_sale = Column(Boolean, default=False)  # New field for sale status
    currency=Column(String(),nullable=True,default='KES')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    email = Column(String, nullable=True,default='')
    phone_number = Column(String, nullable=True,default='')
    country = Column(String, nullable=False,default='Kenya')
    linkedin = Column(String,nullable=True, default='')
    whatsapp = Column(String,nullable=True,default='')
    facebook = Column(String,nullable=True,default='')

    # Relationships
    owner = relationship("User", back_populates="houses")
    reviews = relationship("Review", back_populates="house", cascade="all, delete")
    likes = relationship("Like", back_populates="house", cascade="all, delete")
    bookings = relationship("Booking", back_populates="house", cascade="all, delete")
    cart_items = relationship("Cart", back_populates="house", cascade="all, delete")
    transactions = relationship("Transaction", back_populates="house", cascade="all, delete")

    def check_booking_status(self):
        # If all rooms are booked, change the house status to 'booked'
        if self.booked_rooms >= self.room_count:
            self.status = HouseStatus.booked
            self.on_sale = False  # Automatically set on_sale to False when booked

        # If the house is sold, change the house status to 'sold'
        if self.status == HouseStatus.sold:
            self.on_sale = False  # Set on_sale to False when sold

        # If the house is on sale and rooms are available, keep the house on sale
        if self.status != HouseStatus.booked and self.booked_rooms < self.room_count:
            self.on_sale = True  # Set on_sale to True if house is on sale

        # Update the remaining rooms count
        self.remaining_rooms = self.room_count - self.booked_rooms

        return self.status


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    rating = Column(Integer, nullable=False)
    comment = Column(String)
    house_id = Column(Integer, ForeignKey("houses.id", ondelete="CASCADE"))
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    house = relationship("House", back_populates="reviews")
    user = relationship("User", back_populates="reviews")


class Log(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(String)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    timestamp = Column(DateTime(timezone=True), server_default=func.now())


class Like(Base):
    __tablename__ = "likes"

    id = Column(Integer, primary_key=True, index=True)
    house_id = Column(Integer, ForeignKey("houses.id", ondelete="CASCADE"))
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    house = relationship("House", back_populates="likes")
    user = relationship("User", back_populates="likes")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))

    user = relationship("User", back_populates="refresh_tokens")

    def __repr__(self):
        return f"<RefreshToken(token={self.token}, user_id={self.user_id})>"


# Booking Model (updated for room booking logic)
class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    house_id = Column(Integer, ForeignKey("houses.id", ondelete="CASCADE"))
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    booking_date = Column(DateTime, default=datetime.now(timezone.utc))
    room_count = Column(Integer, nullable=False)  # Number of rooms booked
    total_price = Column(Float, nullable=False)
    guest_count=Column(Integer, nullable=False)
    end_date=Column(DateTime, default=datetime.now(),nullable=False)
    start_date=Column(DateTime, default=datetime.now(),nullable=False)
    booking_type=Column(String,nullable=False)
    special_request=Column(String, nullable=True)
    status=Column(Enum(BookingStatus), default=BookingStatus.PENDING,nullable=True)


    # Relationships
    house = relationship("House", back_populates="bookings")
    user = relationship("User", back_populates="bookings")

    def update_house_booking_status(self):
        house = self.house
        house.booked_rooms += self.room_count  # Update booked rooms count
        house.check_booking_status()  # Check and update house status accordingly


class Cart(Base):
    __tablename__ = "cart"

    id = Column(Integer, primary_key=True, index=True)
    added_at=Column(DateTime(timezone=True), server_default=func.now())
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    house_id = Column(Integer, ForeignKey("houses.id", ondelete="CASCADE"), nullable=False)

    user = relationship("User", back_populates="cart_items")
    house = relationship("House", back_populates="cart_items")
