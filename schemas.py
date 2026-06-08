from pydantic import BaseModel
from typing import Optional
import datetime

# ─── AUTH ────────────────────────────────────────────────

class RegisterIn(BaseModel):
    name     : str
    email    : str
    phone    : str
    password : str

class LoginIn(BaseModel):
    email    : str
    password : str

class LoginOut(BaseModel):
    id_user : int
    name    : str
    email   : str
    token   : str  # JWT token untuk request berikutnya

# ─── PROFILE ─────────────────────────────────────────────

class ProfileIn(BaseModel):
    name   : str
    age    : int
    gender : str
    tb     : float
    bb     : float

class ProfileOut(BaseModel):
    id      : int
    id_user : int
    name    : str
    age     : int
    gender  : str
    tb      : float
    bb      : float
    image_url : Optional[str] = None

    class Config:
        from_attributes = True

# ─── MEASUREMENT ─────────────────────────────────────────

class MeasurementIn(BaseModel):
    id_user    : int
    id_profile : int
    mov        : int
    ihb        : int
    bpm        : int
    dia        : int
    sys        : int
    datetime   : datetime.datetime

class MeasurementOut(BaseModel):
    id         : int
    id_user    : int
    id_profile : int
    sys        : int
    dia        : int
    bpm        : int
    ihb        : bool
    mov        : bool
    datetime   : datetime.datetime

    class Config:
        from_attributes = True

from typing import Optional
from datetime import datetime as dt
from pydantic import BaseModel, Field

# ─── SPO2 MEASUREMENT ────────────────────────────────────

class Spo2MeasurementIn(BaseModel):
    id_user    : int
    id_profile : int
    spo2       : float
    bpm        : float
    temperature: float
    datetime   : Optional[dt] = Field(default_factory=dt.utcnow)

class Spo2MeasurementOut(BaseModel):
    id         : int
    id_user    : int
    id_profile : int
    spo2       : float
    bpm        : float
    temperature: float
    blood_sugar: Optional[float] = None
    datetime   : dt

    class Config:
        from_attributes = True