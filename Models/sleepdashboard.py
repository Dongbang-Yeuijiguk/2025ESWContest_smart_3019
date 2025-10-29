from sqlalchemy import Column, Integer, Float, String, Date, Time, DateTime, JSON
from database import Base



class SleepData(Base):
    __tablename__ = "sleep_data"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, unique=True, index=True)
    sleep_time = Column(DateTime)
    wake_time = Column(DateTime)
    sleep_score = Column(Float)
    breathing = Column(JSON)
    rustle = Column(JSON)
    total_score = Column(Float)
