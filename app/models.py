from sqlalchemy import Column, Integer, String, Boolean, Enum, ForeignKey, DateTime, ARRAY, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.schema import ForeignKeyConstraint
from app.database import Base
import enum


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


# User model
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

    # Additional missing fields
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    country = Column(String, nullable=True)
    state = Column(String, nullable=True)
    address = Column(String, nullable=True)
    zipcode = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)

    # Relationships
    houses = relationship("House", back_populates="owner", cascade="all, delete")
    reviews = relationship("Review", back_populates="user", cascade="all, delete")
    likes = relationship("Like", back_populates="user", cascade="all, delete")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete")
    bookings = relationship("Booking", back_populates="user", cascade="all, delete")
    cart_items = relationship("Cart", back_populates="user", cascade="all, delete")

    # Add any additional relationships if needed, for example:
    # user_settings = relationship("UserSetting", back_populates="user", cascade="all, delete")

class House(Base):
    __tablename__ = "houses"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(String)
    price = Column(Integer, nullable=False)
    location = Column(String, index=True)
    image_urls = Column(ARRAY(String))
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    is_approved = Column(Boolean, default=False)
    availability = Column(Boolean, default=True)
    room_count = Column(Integer, nullable=False)
    type = Column(Enum(HouseType))
    amenities = Column(ARRAY(String))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    owner = relationship("User", back_populates="houses")
    reviews = relationship("Review", back_populates="house", cascade="all, delete")
    likes = relationship("Like", back_populates="house", cascade="all, delete")
    bookings = relationship("Booking", back_populates="house", cascade="all, delete")
    cart_items = relationship("Cart", back_populates="house", cascade="all, delete")


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


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    house_id = Column(Integer, ForeignKey("houses.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    total_price = Column(Float, nullable=False)
    rooms_no = Column(Integer, default=1, nullable=False)
    status = Column(Enum(BookingStatus), default=BookingStatus.PENDING, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    house = relationship("House", back_populates="bookings")
    user = relationship("User", back_populates="bookings")


class Cart(Base):
    __tablename__ = "cart"

    id = Column(Integer, primary_key=True, index=True)
    added_at=Column(DateTime(timezone=True), server_default=func.now())
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    house_id = Column(Integer, ForeignKey("houses.id", ondelete="CASCADE"), nullable=False)

    user = relationship("User", back_populates="cart_items")
    house = relationship("House", back_populates="cart_items")
