from enum import Enum

from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Any


class RoutineType(str, Enum):
    outside = "outside"
    inside = "inside"
    sleep = "sleep"
    wake = "wake"
    manual = "manual"
    voice = "voice"
    rest = "rest"
    pre_sleep = "pre_sleep"
    nap = "nap"


class LogBase(BaseModel):
    id :int
    start_time: datetime
    routine_type: RoutineType
    routine_id: Optional[int] = None
    change: Optional[Any] = None

class LogCreate(BaseModel):
    start_time: datetime
    routine_type: RoutineType
    routine_id: Optional[int] = None
    change: Optional[Any] = None # json 형식
