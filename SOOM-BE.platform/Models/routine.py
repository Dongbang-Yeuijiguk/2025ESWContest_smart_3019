from sqlalchemy import Column, Integer, Enum, Float, Time, String, DateTime
import enum

from sqlalchemy.orm import relationship

from database import Base

class DevicePower(enum.Enum):
    on = "on"
    off = "off"

 # 루틴 타입
class RoutineType(enum.Enum):
    outside = "outside"
    inside = "inside"
    sleep = "sleep"
    wake = "wake"
    during_sleep = "during_sleep"
    voice = "voice"
    manual= "manual"


# 루틴 상태
class Status(enum.Enum):
    enroll = "enroll"
    dismissed = "dismissed"
    pause = "pause"

# 에어컨 모드
class ACTargetMode(enum.Enum):
    slow = "slow"
    low = "low"
    mid = "mid"
    high = "high"
    power = "power"
    auto = "auto"

# 공기청정기 타겟 모드
class APTargetMode(enum.Enum):
    slow = "slow"
    low = "low"
    mid = "mid"
    high = "high"
    power = "power"
    auto = "auto"

class Routine(Base):
    __tablename__ = "routine"
    id = Column(Integer, primary_key=True, index=True)
    routine_type = Column(Enum(RoutineType), nullable=False)
    status = Column(Enum(Status), nullable=False)
    set_time = Column(Time, nullable=True)
    alarm_type = Column(String(255), nullable=True)
    recall = Column(Integer, nullable=True)


    # 에어컨
    ac_power = Column(Enum(DevicePower), nullable=True)
    target_ac_temperature = Column(Float, nullable=True)
    target_ac_humidity = Column(Float, nullable=True)
    target_ac_mode = Column(Enum(ACTargetMode), nullable=True)

    # 공기청정기
    ap_power = Column(Enum(DevicePower), nullable=True)
    target_ap_pm = Column(Float, nullable=True)
    target_ap_mode = Column(Enum(APTargetMode), nullable=True)

    # 전등
    light_power = Column(Enum(DevicePower), nullable=True)
    light_temperature = Column(Integer, nullable=True)
    target_light_level = Column(Integer, nullable=True)

    #커튼
    curtain = Column(Enum(DevicePower), nullable=True)  # on: 밖에 안보이는거, off : 밖이 보이는거

    log = relationship("ControlLog",back_populates="routine")
