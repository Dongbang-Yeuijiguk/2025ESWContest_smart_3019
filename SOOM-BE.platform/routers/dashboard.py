from fastapi import APIRouter, Depends, HTTPException
from datetime import date, timedelta
import asyncio

from starlette.responses import JSONResponse
from starlette.websockets import WebSocket, WebSocketDisconnect
from Models.sleepdashboard import SleepData
from Models.user import User
from database import get_db
from sqlalchemy.orm import Session
from util.util import analyze_rustle_movement,analyze_breathing, get_latest_values


router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])

@router.get("/sleep/report/{indate}", response_model=dict)
async def get_sleep_analysis(indate: date, db: Session = Depends(get_db)):
    """
    요청한 날짜 기준 수면 리포트 + 최근 7일 패턴 반환 (딕셔너리 형태)
    """
    target_date = indate - timedelta(days=1)

    # 해당 날짜 리포트 조회
    query = db.query(SleepData).filter(SleepData.date == target_date).first()
    if query is None:
        raise HTTPException(status_code=404, detail="Sleep data not found")

    # 최근 7일 데이터 조회
    start_date = target_date - timedelta(days=6)
    weekly_data = (
        db.query(SleepData)
        .filter(SleepData.date.between(start_date, target_date))
        .order_by(SleepData.date)
        .all()
    )

    # 주간 패턴 구성
    weekly_pattern = []
    for record in weekly_data:
        weekly_pattern.append({
            "date": record.date.isoformat(),
            "sleep_start": record.sleep_time.strftime("%H:%M") if record.sleep_time else None,
            "sleep_end": record.wake_time.strftime("%H:%M") if record.wake_time else None,
            "score": round(record.total_score, 1) if record.total_score else None
        })

    # 하루 리포트 데이터 구성
    result = {
        "date": query.date.isoformat(),
        "sleep_time": query.sleep_time.isoformat() if query.sleep_time else None,
        "wake_time": query.wake_time.isoformat() if query.wake_time else None,
        "sleep_score" : query.sleep_score,
        "breathing": query.breathing or {},
        "rustle": query.rustle or {},
        "total_quality_score": round(query.total_score, 2) if query.total_score else None,
        "weekly_pattern": weekly_pattern
    }

    return result

@router.post("/analysis/create/{indate}")
async def create_data(indate: date, db: Session = Depends(get_db)):
    """
    전날 수면 시간 구간을 기반으로 호흡, 뒤척임, 수면깊이 분석 후 결과 반환
    """
    # 분석 대상 날짜 (전날)
    target_date = indate - timedelta(days=1)

    # 전날 수면 시작/종료 시간 가져오기
    query = db.query(User).filter(User.date == target_date).first()

    if query is None:
        raise HTTPException(status_code=404, detail=f"No sleep data found for {target_date}")

    sleep_time = query.sleep_time
    wake_time = query.wake_time

    # 분석 실행
    breathing_result = analyze_breathing(sleep_time, wake_time)
    rustle_result = analyze_rustle_movement(sleep_time, wake_time)
    #sleep_depth_result = analyze_sleep_depth(sleep_time, wake_time)

    # 전체 수면 품질 점수 계산
    breathing_score = breathing_result.get("score", 0) # 호흡
    rustle_score = rustle_result.get("score", 0)  # 뒤척임


    sleep_duration = (wake_time - sleep_time).total_seconds() / 3600  # 시간 단위

    if sleep_duration < 5:
        score_H = 40
    elif 5 <= sleep_duration < 7:
        score_H = 70
    elif 7 <= sleep_duration <= 9:
        score_H = 100
    else:
        score_H = 80

    start_range = target_date - timedelta(days=6)
    past_week = db.query(User).filter(User.date.between(start_range, target_date)).all()

    if not past_week or len(past_week) < 3:
        rhythm_score = 80  # 데이터 부족 시 기본 점수

    else:
        # 평균 취침/기상 시각 계산
        avg_sleep_minutes = sum(
            (r.sleep_time.hour * 60 + r.sleep_time.minute) for r in past_week
        ) / len(past_week)
        avg_wake_minutes = sum(
            (r.wake_time.hour * 60 + r.wake_time.minute) for r in past_week
        ) / len(past_week)

        # 전날 편차 계산 (절대값)
        sleep_minutes = sleep_time.hour * 60 + sleep_time.minute
        wake_minutes = wake_time.hour * 60 + wake_time.minute

        sleep_diff = abs(sleep_minutes - avg_sleep_minutes)
        wake_diff = abs(wake_minutes - avg_wake_minutes)
        total_diff = sleep_diff + wake_diff

        # 리듬 점수 계산 (편차 0분 → 100점, 120분 이상 → 0점)
        if total_diff < 30:
            rhythm_score = 100
        else :
            rhythm_score = max(0,100-((total_diff-30)/150) *100)


    total_quality_score = round(
        (breathing_score or 0) * 0.25 + (rustle_score or 0) * 0.25 + (score_H or 0) * 0.3 + (rhythm_score *0.2 or 0),2
    )

    # 🔹 5. 스키마 데이터 구성
    data = SleepData(
        date=target_date,
        sleep_time=sleep_time,
        wake_time=wake_time,
        sleep_score = score_H,
        breathing=breathing_result,
        rustle=rustle_result,
        total_score=total_quality_score
    )
    db.add(data)
    db.commit()
    db.refresh(data)
    # 결과 반환
    return  JSONResponse(status_code=200, content="data.dict()")


@router.post("/analysis/delete/{indate}")
async def delete_data(indate: date, db: Session = Depends(get_db)):
    query = db.query(SleepData).filter(SleepData.date == indate).first()
    if query is None:
        raise HTTPException(status_code=404, detail=f"No sleep data found for {indate}")

    db.delete(query)
    db.commit()
    return JSONResponse(status_code=200, content="delete success")


@router.websocket("/ws/environment/current")
async def dashboard(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = get_latest_values()
            print(data)
            await websocket.send_json(data)
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        print("websocket disconnect")
    except Exception as e:
        print(f"exception : {e}")
    finally:
        try:
            await websocket.close()
        except RuntimeError:
            pass
