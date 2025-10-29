from pydantic import BaseModel, Field
from typing import Optional, Literal
from enum import Enum
from Models.routine import RoutineType
from datetime import time, datetime


# Enum 정의 (SQLAlchemy와 동일하게)
class DevicePower(str, Enum):
    on = "on"
    off = "off"

class Status(str, Enum):
    enroll = "enroll"
    dismissed = "dismissed"
    pause = "pause"

class AQTargetMode(str, Enum):
    slow = "slow"
    low = "low"
    mid = "mid"
    high = "high"
    power = "power"
    auto = "auto"

class APTargetMode(str, Enum):
    slow = "slow"
    low = "low"
    mid = "mid"
    high = "high"
    power = "power"
    auto = "auto"


# 공통 베이스 스키마
class RoutineBase(BaseModel):
    routine_type: RoutineType
    status: Status
    set_time: Optional[time] = None
    alarm_type: Optional[str] = None
    recall: Optional[int] = None

    ac_power: Optional[DevicePower] = None
    target_ac_temperature: Optional[float] = None
    target_ac_humidity: Optional[float] = None
    target_ac_mode: Optional[AQTargetMode] = None

    ap_power: Optional[DevicePower] = None
    target_ap_pm: Optional[float] = None
    target_ap_mode: Optional[APTargetMode] = None

    light_power: Optional[DevicePower] = None
    light_temperature: Optional[int] = None
    target_light_level: Optional[int] = None

    curtain: Optional[DevicePower] = None


# 생성 요청용
class RoutineCreate(RoutineBase):
    pass


# 수정용 (선택적으로 모든 필드)
class RoutineUpdate(BaseModel):
    routine_type: Optional[RoutineType] = None
    status: Optional[Status] = None
    set_time : Optional[datetime] = None
    alarm_type: Optional[str] = None
    recall : Optional[int] = None

    ac_power: Optional[DevicePower] = None
    target_ac_temperature: Optional[float] = None
    target_ac_humidity: Optional[float] = None
    target_ac_mode: Optional[AQTargetMode] = None

    ap_power: Optional[DevicePower] = None
    target_ap_pm: Optional[float] = None
    target_ap_mode: Optional[APTargetMode] = None

    light_power: Optional[DevicePower] = None
    light_temperature: Optional[int] = None
    target_light_level: Optional[int] = None

    curtain: Optional[DevicePower] = None


# 응답용
class RoutineRead(RoutineBase):
    id: int

    model_config = {
        "from_attributes": True  # SQLAlchemy 모델에서 변환 시 사용
    }
