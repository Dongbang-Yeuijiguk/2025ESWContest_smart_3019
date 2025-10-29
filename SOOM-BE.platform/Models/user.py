from sqlalchemy import Column, Integer, Date, DateTime
from database import Base

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)

    # 실제 값
    wake_time = Column(DateTime, nullable=True)
    sleep_time = Column(DateTime, nullable=True)
    in_time = Column(DateTime, nullable=True)
    out_time = Column(DateTime, nullable=True)
    return_time = Column(DateTime, nullable=True)

    # 예측 값
    predicted_wake_time = Column(DateTime, nullable=True)
    predicted_sleep_time = Column(DateTime, nullable=True)
    predicted_in_time = Column(DateTime, nullable=True)
    predicted_out_time = Column(DateTime, nullable=True)
    predicted_return_time = Column(DateTime, nullable=True)