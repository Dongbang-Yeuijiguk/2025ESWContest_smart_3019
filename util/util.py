from collections import defaultdict

from influxdb_client import InfluxDBClient
from influxdb_client.client.query_api import QueryApi
from datetime import datetime
import os
from dotenv import load_dotenv
from zoneinfo import ZoneInfo
load_dotenv()

# 설정
INFLUX_URL = os.getenv("INFLUXDB_URL")
INFLUX_TOKEN = os.getenv("INFLUXDB_TOKEN")
INFLUX_ORG = os.getenv("INFLUXDB_ORG")
INFLUX_BUCKET = os.getenv("INFLUXDB_BUCKET")

client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
query_api: QueryApi = client.query_api()

def get_latest_values():

    measurements = [
        "aircondition_sensor",
        "air_purifier_sensor",
        "smart_curtain",
        "smart_light"
    ]

    data = {}
    for measurement in measurements:
        query = f'''
        from(bucket: "{INFLUX_BUCKET}")
          |> range(start: -5m)
          |> filter(fn: (r) => r._measurement == "{measurement}")
          |> group(columns: ["_field"])
          |> last()
        '''

        tables = query_api.query(query=query, org=INFLUX_ORG)
        for table in tables:
            for record in table.records:
                field = record.get_field()
                value = record.get_value()
                data[f"{measurement}_{field}"] = value

    new_data = {
        "temperature": data.get("aircondition_sensor_temperature"),
        "humidity": data.get("aircondition_sensor_humidity"),
        "curtain": data.get("smart_curtain_power"),
        "air_quality": data.get("air_purifier_sensor_aqi"),
        "pm_2_5": data.get("air_purifier_sensor_pm_2_5"),
        "pm_10": data.get("air_purifier_sensor_pm_10"),
    }
    return new_data

def analyze_breathing(start_time: datetime, end_time: datetime) -> dict:
    """
    수면 시작~종료 시간 사이의 호흡수 분석 (bpm), conf ≥ 0.6 필터
    :param start_time: 수면 시작 시간 (datetime, KST)
    :param end_time: 수면 종료 시간 (datetime, KST)
    :return: dict(average_bpm, per_minute_bpm[], data_points)
    """
    kst = ZoneInfo("Asia/Seoul")
    utc = ZoneInfo("UTC")

    # 1. 입력 시간을 KST로 간주하고 UTC로 변환
    # 입력 start_time에 타임존 정보가 없으면 KST를 지정 후, UTC로 변환합니다.
    if start_time.tzinfo is None:
        start_aware = start_time.replace(tzinfo=kst)
    else:
        start_aware = start_time

    if end_time.tzinfo is None:
        end_aware = end_time.replace(tzinfo=kst)
    else:
        end_aware = end_time

    # start, end 변수에 UTC 시간 문자열을 저장합니다.
    start = start_aware.astimezone(utc).isoformat()
    end = end_aware.astimezone(utc).isoformat()

    flux_query = f"""
    import "join"

    mean = from(bucket: "{INFLUX_BUCKET}")
      |> range(start: time(v: "{start}"), stop: time(v: "{end}"))
      |> filter(fn: (r) => r._measurement == "sleep_data")
      |> filter(fn: (r) => r._field == "bpm" or r._field == "bpm_conf" or r._field == "movement_conf")
      |> aggregateWindow(every: 10m, fn: mean, createEmpty: false)
      |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
      |> filter(fn: (r) => exists r.bpm and exists r.bpm_conf and exists r.movement_conf and r.bpm_conf >= 0.6 and r.movement_conf >= 0.6)
      |> keep(columns: ["_time", "bpm", "bpm_conf", "movement_conf"])
      |> rename(columns: {{bpm: "mean_bpm"}})

    max = from(bucket: "{INFLUX_BUCKET}")
      |> range(start: time(v: "{start}"), stop: time(v: "{end}"))
      |> filter(fn: (r) => r._measurement == "sleep_data")
      |> filter(fn: (r) => r._field == "bpm" or r._field == "bpm_conf" or r._field == "movement_conf")
      |> aggregateWindow(every: 10m, fn: max, createEmpty: false)
      |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
      |> filter(fn: (r) => exists r.bpm and exists r.bpm_conf and exists r.movement_conf and r.bpm_conf >= 0.6 and r.movement_conf >= 0.6)
      |> keep(columns: ["_time", "bpm"])
      |> rename(columns: {{bpm: "max_bpm"}})

    min = from(bucket: "{INFLUX_BUCKET}")
      |> range(start: time(v: "{start}"), stop: time(v: "{end}"))
      |> filter(fn: (r) => r._measurement == "sleep_data")
      |> filter(fn: (r) => r._field == "bpm" or r._field == "bpm_conf" or r._field == "movement_conf")
      |> aggregateWindow(every: 10m, fn: min, createEmpty: false)
      |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
      |> filter(fn: (r) => exists r.bpm and exists r.bpm_conf and exists r.movement_conf and r.bpm_conf >= 0.6 and r.movement_conf >= 0.6)
      |> keep(columns: ["_time", "bpm"])
      |> rename(columns: {{bpm: "min_bpm"}})

    join1 = join.time(
      left: mean,
      right: max,
      as: (l, r) => ({{ 
        _time: l._time,
        mean_bpm: l.mean_bpm,
        bpm_conf: l.bpm_conf,
        movement_conf: l.movement_conf,
        max_bpm: r.max_bpm
      }})
    )

    join2 = join.time(
      left: join1,
      right: min,
      as: (l, r) => ({{ 
        _time: l._time,
        mean_bpm: l.mean_bpm,
        max_bpm: l.max_bpm,
        bpm_conf: l.bpm_conf,
        movement_conf: l.movement_conf,
        min_bpm: r.min_bpm
      }})
    )

    join2
      |> keep(columns: ["_time", "mean_bpm", "max_bpm", "min_bpm", "bpm_conf", "movement_conf"])
    """

    tables = query_api.query(query=flux_query)

    total_bpm = 0
    total_score = 0
    count = 0
    per_minute_bpm = []
    unbreathing_events = []

    for table in tables:
        for record in table.records:
            time = record.get_time()
            bpm = round(record.values.get("mean_bpm"),2)
            max_bpm = round(record.values.get("max_bpm"),2)
            min_bpm = round(record.values.get("min_bpm"),2)
            if bpm is not None:
                time_str = time.isoformat()
                per_minute_bpm.append({"time": time_str, "bpm": bpm,"max_bpm" : max_bpm, "min_bpm" : min_bpm})
                total_bpm += bpm
                count += 1

                # 무호흡 이벤트 기록
                if bpm < 6:
                    unbreathing_events.append({"time": time_str, "bpm": bpm})

                # 수면 점수 계산
                if bpm < 6 :
                    score = 30
                elif 6 <= bpm < 12:
                    score = ((bpm - 6) / 6) * 100
                elif 12 <= bpm <= 20:
                    score = 100
                elif 20 < bpm <= 30:
                    score = 100 - ((bpm - 20) / 10) * 100
                    score = max(score, 0)
                else:
                    score = 0

                total_score += score

    avg_bpm = total_bpm / count if count > 0 else None
    avg_score = total_score / count if count > 0 else None
    print(total_score)
    return {
        "average_bpm": round(avg_bpm,2),
        "records": per_minute_bpm,
        "unbreathing_events": unbreathing_events,
        "total_count": count,
        "score": round(avg_score, 2) if avg_score is not None else None
    }


def analyze_rustle_movement(start_time: datetime, end_time: datetime):
    kst = ZoneInfo("Asia/Seoul")
    utc = ZoneInfo("UTC")

    # KST -> UTC로 변환
    if start_time.tzinfo is None:
        start_aware = start_time.replace(tzinfo=kst)
    else:
        start_aware = start_time

    if end_time.tzinfo is None:
        end_aware = end_time.replace(tzinfo=kst)
    else:
        end_aware = end_time

    # start, end 변수에 UTC 시간 문자열을 저장합니다.
    start = start_aware.astimezone(utc).isoformat()
    end = end_aware.astimezone(utc).isoformat()

    # rustle만 필터 후 2분 단위 count 집계
    flux_query = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: {start}, stop: {end})
      |> filter(fn: (r) => r._measurement == "sleep_data")
      |> filter(fn: (r) => r["movement"] == "rustle")
      |> aggregateWindow(every: 2m, fn: count, createEmpty: true)
      |> filter(fn: (r) => r._value > 0)
      |> keep(columns: ["_time", "_value"])
      |> yield(name: "rustle_only")
    '''

    tables = query_api.query(query=flux_query)

    result = []

    for table in tables:
        for record in table.records:
            time = record.get_time()

            result.append({
                "start": time.isoformat()
            })

    total_sleep_time = (end_time - start_time).total_seconds() / 60
    rustle_time = len(result) * 2
    rustle_ratio = rustle_time/total_sleep_time * 100  if total_sleep_time > 0 else 0

    if rustle_ratio <= 10:
        score = 100
    else:
        score = 100 - ((rustle_ratio - 10) / 20) * 100
        score = max(0, round(score, 2))

    return {
        "records": result,
        "total_count": len(result),
        "score" : score
    }

def get_state() :
    flux_query = f'''
        from(bucket: "{INFLUX_BUCKET}")
          |> range(start: -5m)
          |> filter(fn: (r) => r._measurement == "state_data")
          |> last()
        '''
    try:
        tables = query_api.query(flux_query)

        for table in tables:
            for record in table.records:
                current_state = record.values.get("state")
                if current_state:
                    return current_state

        return None

    except Exception as e:
        return None