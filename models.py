from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Float, Index
from sqlalchemy.orm import relationship
from database import Base
import datetime


class User(Base):
    __tablename__ = "users"

    id       = Column(Integer, primary_key=True, index=True)
    name     = Column(String, nullable=False)
    email    = Column(String, unique=True, nullable=False, index=True)
    phone    = Column(String, unique=True, nullable=False, index=True)
    password = Column(String, nullable=False)

    profiles     = relationship("Profile", back_populates="user")
    measurements = relationship("Measurement", back_populates="user")
    spo2_measurements = relationship("Spo2Measurement", back_populates="user")


class Profile(Base):
    __tablename__ = "profiles"

    id      = Column(Integer, primary_key=True, index=True)
    id_user = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name    = Column(String, nullable=False)  # "Ayah", "Ibu", dll
    age     = Column(Integer, nullable=False)
    gender  = Column(String, nullable=False)
    tb      = Column(Float, nullable=False)
    bb      = Column(Float, nullable=False)
    image_path = Column(String, nullable=True)

    user         = relationship("User", back_populates="profiles")
    measurements = relationship("Measurement", back_populates="profile")
    spo2_measurements = relationship("Spo2Measurement", back_populates="profile")


class Measurement(Base):
    __tablename__ = "measurements"
    __table_args__ = (
        Index("ix_meas_user_profile", "id_user", "id_profile"),
        Index("ix_meas_profile_user_dt", "id_profile", "id_user", "datetime"),
    )

    id         = Column(Integer, primary_key=True, index=True)
    id_user    = Column(Integer, ForeignKey("users.id"), nullable=False)
    id_profile = Column(Integer, ForeignKey("profiles.id"), nullable=False)
    sys        = Column(Integer, nullable=False)
    dia        = Column(Integer, nullable=False)
    bpm        = Column(Integer, nullable=False)
    ihb        = Column(Boolean, default=False)
    mov        = Column(Boolean, default=False)
    datetime   = Column(DateTime, default=datetime.datetime.utcnow, index=True)

    user    = relationship("User", back_populates="measurements")
    profile = relationship("Profile", back_populates="measurements")


class Spo2Measurement(Base):
    __tablename__ = "spo2_measurements"
    __table_args__ = (
        Index("ix_spo2_user_profile", "id_user", "id_profile"),
        Index("ix_spo2_profile_user_dt", "id_profile", "id_user", "datetime"),
    )

    id         = Column(Integer, primary_key=True, index=True)
    id_user    = Column(Integer, ForeignKey("users.id"), nullable=False)
    id_profile = Column(Integer, ForeignKey("profiles.id"), nullable=False)
    spo2       = Column(Float, nullable=False)
    bpm        = Column(Float, nullable=False)
    temperature= Column(Float, nullable=False)
    blood_sugar= Column(Float, nullable=True)
    datetime   = Column(DateTime, default=datetime.datetime.utcnow, index=True)

    user    = relationship("User", back_populates="spo2_measurements")
    profile = relationship("Profile", back_populates="spo2_measurements")