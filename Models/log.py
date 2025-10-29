from sqlalchemy import Column, Integer, Enum, DateTime, ForeignKey, JSON
import enum
from database import Base
from sqlalchemy.orm import relationship

class RoutineTypeLog(enum.Enum):
    outside = "outside"
    inside = "inside"
    sleep = "sleep"
    wake = "wake"
    manual = "manual"
    voice = "voice"
    rest = "rest"
    pre_sleep = "pre_sleep"
    nap = "nap"

class ControlLog(Base):
    __tablename__ = 'controllog'

    id = Column(Integer, primary_key=True)
    start_time = Column(DateTime, nullable=False)
    routine_type = Column(Enum(RoutineTypeLog), nullable=False)
    routine_id = Column(ForeignKey("routine.id"), nullable=True)
    change = Column(JSON, nullable=True)

    routine = relationship("Routine", back_populates="log")
