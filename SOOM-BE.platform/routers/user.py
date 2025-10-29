from datetime import date, timedelta
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse
from Models.user import User
from schemas.user import UserCreate,UserResponse,UserDefault,WakeTimeRequest,UserBase
from database import get_db
from Models.log import ControlLog
from util.util import get_state
router = APIRouter(prefix="/api/v1/user", tags=["user"])

@router.post("/create", response_model=UserResponse)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    user = User(**user.dict())
    db.add(user)
    db.commit()
    db.refresh(user)

    return user

@router.post("/delete")
def delete_user(date: date, db : Session = Depends(get_db)):
    query = db.query(User).filter(User.date == date).first()
    if not query:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(query)
    db.commit()
    return JSONResponse(status_code=200, content="delete success")


@router.get("/default", response_model=UserDefault)
def read_default_user(db: Session = Depends(get_db)):
    target_date = date.today()
    user = db.query(User).filter(User.date == target_date).first()

    last_control = (
        db.query(ControlLog)
        .filter(ControlLog.routine_type != "manual")
        .order_by(ControlLog.id.desc())
        .first()
    )
    if not last_control:
        raise HTTPException(status_code=404, detail="ControlLog not found")

    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    data = UserDefault.model_validate(user)
    data["routine_type"] = last_control.routine_type

    return data


@router.post("/set")
def set_user(data :WakeTimeRequest, db: Session = Depends(get_db)):
    query = db.query(User).filter(User.date == data.date).first()
    if not query:
        raise HTTPException(status_code=404, detail="settings not found")
    if query.predicted_wake_time is None:
        query.predicted_wake_time = data.predicted_wake_time

    if query.predicted_sleep_time is None:
        query.predicted_sleep_time = data.predicted_wake_time-timedelta(hours=7)

    return_time = query.predicted_sleep_time
    db.commit()
    db.refresh(query)
    return {"predicted_sleep_time": return_time}

@router.get("/get/{indata}")
def get_user(date: date,db: Session = Depends(get_db)):
    query = db.query(User).filter(User.date == date).first()
    if not query:
        raise HTTPException(status_code=404, detail="user not found")
    data = UserBase.model_validate(query)
    return data