from pydantic import BaseModel
from typing import Optional
from datetime import time, date, datetime


class UserBase(BaseModel):
    date: date

    wake_time: Optional[datetime] = None
    sleep_time: Optional[datetime] = None
    in_time: Optional[datetime]= None
    out_time: Optional[datetime]= None
    return_time: Optional[datetime]= None

    # 예측 값
    predicted_wake_time: Optional[datetime]= None
    predicted_sleep_time: Optional[datetime]= None
    predicted_in_time: Optional[datetime] = None
    predicted_out_time: Optional[datetime] = None
    predicted_return_time: Optional[datetime] = None

    model_config = {"arbitrary_types_allowed": True,
                    "from_attributes": True}

class UserCreate(UserBase):
    pass


class UserResponse(UserBase):
    id: int

    model_config = {"arbitrary_types_allowed": True,
                    "from_attributes": True}

class UserDefault(BaseModel):
    predicted_wake_time: Optional[datetime] = None
    predicted_sleep_time: Optional[datetime] = None
    state : Optional[str] = None
    routine_type: Optional[str] = None

    model_config = {"arbitrary_types_allowed": True,
                    "from_attributes": True}

class WakeTimeRequest(BaseModel):
    date: date
    predicted_wake_time: datetime