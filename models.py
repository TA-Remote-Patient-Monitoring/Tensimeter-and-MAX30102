from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship
from database import Base
import datetime

class User(Base):
    __tablename__ = "users"

    id       = Column(Integer, primary_key=True, index=True)
    name     = Column(String, nullable=False)
    email    = Column(String, unique=True, nullable=False)
    phone    = Column(String, nullable=False)
    password = Column(String, nullable=False)

    profiles     = relationship("Profile", back_populates="user")
    measurements = relationship("Measurement", back_populates="user")


class Profile(Base):
    __tablename__ = "profiles"

    id      = Column(Integer, primary_key=True, index=True)
    id_user = Column(Integer, ForeignKey("users.id"), nullable=False)
    name    = Column(String, nullable=False)  # "Ayah", "Ibu", dll
    age     = Column(Integer, nullable=False)
    gender  = Column(String, nullable=False)
    tb      = Column(Float, nullable=False)
    bb      = Column(Float, nullable=False)
    image_path = Column(String, nullable=True)

    user         = relationship("User", back_populates="profiles")
    measurements = relationship("Measurement", back_populates="profile")


class Measurement(Base):
    __tablename__ = "measurements"

    id         = Column(Integer, primary_key=True, index=True)
    id_user    = Column(Integer, ForeignKey("users.id"), nullable=False)
    id_profile = Column(Integer, ForeignKey("profiles.id"), nullable=False)
    sys        = Column(Integer, nullable=False)
    dia        = Column(Integer, nullable=False)
    bpm        = Column(Integer, nullable=False)
    ihb        = Column(Boolean, default=False)
    mov        = Column(Boolean, default=False)
    datetime   = Column(DateTime, default=datetime.datetime.utcnow)

    user    = relationship("User", back_populates="measurements")
    profile = relationship("Profile", back_populates="measurements")