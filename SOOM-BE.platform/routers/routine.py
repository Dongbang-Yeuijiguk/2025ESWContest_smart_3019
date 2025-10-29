from fastapi import APIRouter, Depends,HTTPException
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse
from util.util import get_state
from database import get_db
from Models.log import ControlLog
from Models.routine import Routine,Status, RoutineType
from Models.user import User
from schemas.routine import RoutineCreate, RoutineRead
from schemas.log import LogCreate
from datetime import timedelta, date,datetime

router = APIRouter(prefix="/api/v1/routine", tags=["routine"])


@router.post("/create")
async def create_routine(data: RoutineCreate, db: Session = Depends(get_db)):
    existing_routine = db.query(Routine).filter(Routine.routine_type == data.routine_type).first()
    today = date.today()

    # 받은 데이터를 딕셔너리로 변환
    routine_data = data.dict(exclude_unset=True)

    if existing_routine:

        for key, value in routine_data.items():
            setattr(existing_routine, key, value)

        db.add(existing_routine)
        db.commit()
        db.refresh(existing_routine)

        return JSONResponse(status_code=200, content={"message": f"루틴 ({data.routine_type})이(가) 성공적으로 업데이트되었습니다."})

    else:
        new_routine = Routine(**routine_data)
        db.add(new_routine)

        query = db.query(User).filter(User.date == today).first()

        set_time_datetime = datetime.combine(today, data.set_time)
        if query is None:
            # 유저가 없을 경우: 새로 생성
            new_user = User(date=today)

            if data.routine_type == RoutineType.sleep:
                new_user.predicted_sleep_time = set_time_datetime
                new_user.predicted_wake_time = set_time_datetime + timedelta(hours=7)

            elif data.routine_type == RoutineType.wake:
                new_user.predicted_wake_time = set_time_datetime
                new_user.predicted_sleep_time = set_time_datetime - timedelta(hours=7)

            db.add(new_user)

        else:
            # 유저가 있을 경우: 조건에 따라 시간 설정
            if data.routine_type == RoutineType.sleep and query.predicted_sleep_time is None:
                query.predicted_sleep_time = set_time_datetime
                if query.predicted_wake_time is None:
                    query.predicted_wake_time = set_time_datetime + timedelta(hours=7)

            elif data.routine_type == RoutineType.wake and query.predicted_wake_time is None:
                query.predicted_wake_time = set_time_datetime
                if query.predicted_sleep_time is None:
                    query.predicted_sleep_time = set_time_datetime - timedelta(hours=7)

        db.commit()
        db.refresh(new_routine)

        return JSONResponse(status_code=201, content={"message": "create routine success."})


@router.get("/state",response_model=dict)
async def get_routine_state():
    result = get_state()
    if result is None:
        return {}
    else :
        return {
            "state": result.get("state")
        }


@router.post("/device")
async def create_log(data: LogCreate, db: Session = Depends(get_db)):
    if data.routine_type == "manual":
        log = ControlLog(
            start_time=data.start_time,
            routine_type=data.routine_type.value,
            routine_id=data.routine_id,
            change=data.change
        )
        db.add(log)
        db.commit()
        return JSONResponse(status_code=200, content = "save_success")
    
    # 유효한 루틴 조회
    query = db.query(Routine).filter(
        Routine.routine_type == data.routine_type,
        Routine.status != Status.dismissed
    ).first()

    if not query:
        raise HTTPException(status_code=404, detail="Routine not found")

    # ControlLog 저장
    log = ControlLog(
        start_time=data.start_time,
        routine_type=data.routine_type.value,
        routine_id=data.routine_id,
        change=data.change
    )
    db.add(log)

    # sleep 또는 wake일 경우, User 테이블에도 저장

    if data.routine_type.value in ["sleep", "wake"]:
        # 루틴 타입에 따라 날짜 조정
        if data.routine_type.value == "wake":
            date_key = (data.start_time - timedelta(days=1)).date()
        else:
            date_key = data.start_time.date()
        print(date_key)
        user = db.query(User).filter_by(date=date_key).first()
        if not user:
            user = User(date=date_key)
            db.add(user)

        # 루틴 타입에 따라 수면 또는 기상 시간 설정
        if data.routine_type.value == "sleep":
            user.sleep_time = data.start_time
        elif data.routine_type.value == "wake":
            user.wake_time = data.start_time

    # 커밋
    db.commit()

    return JSONResponse(status_code=201, content={"message": "save success"})


@router.get("/{routine_type}",response_model=RoutineRead)
def get_routine(routine_type: str, db: Session = Depends(get_db)):
    routine_enum = RoutineType[routine_type]
    query = db.query(Routine).filter(Routine.routine_type == routine_enum).first()


    if not query:
        raise HTTPException(status_code=404, detail="Routine not found")

    routine = RoutineRead.model_validate(query)
    print(query)
    return routine

