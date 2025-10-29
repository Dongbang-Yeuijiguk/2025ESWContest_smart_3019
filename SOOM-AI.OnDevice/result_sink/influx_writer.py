from zoneinfo import ZoneInfo
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
import config
from datetime import datetime

# 한국 시간대 설정
KST = ZoneInfo("Asia/Seoul")

class InfluxWriter:
    """
    InfluxDB에 AI 추론 결과와 수면 상태 변화를 각각 다른 Measurement에 저장합니다.
    """
    def __init__(self, url, token, org):
        print(f"Connecting to InfluxDB... ({url})")
        self.client = InfluxDBClient(url=url, token=token, org=org)
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
        print("Connection to result sink completed.")

    def write_result(self, result: dict):
        """
        AI 추론 결과 (movement, bpm 등)를 메인 Measurement에 저장합니다.
        
        Args:
            result (dict): {'status': 'present', 'movement': 'sitting', ...} 형태의 딕셔너리
        """
        try:
            # ✨ [수정 1] ✨
            # result 딕셔너리에서 timestamp를 찾지 않고, 현재 KST 시간을 직접 사용합니다.
            timestamp_now_kst = datetime.now(KST)
            
            # config.py에 정의된 측정 이름 사용 (원본 코드의 "sleep_data" 대신)
            point = Point(config.INFLUX_WRITE_MEASUREMENT) \
                .tag("status", result.get("status", "UNKNOWN")) \
                .tag("movement", result.get("movement", "UNKNOWN")) \
                .field("movement_conf", float(result.get("movement_conf", 0.0))) \
                .field("bpm", float(result.get("bpm", 0.0))) \
                .field("bpm_conf", float(result.get("bpm_conf", 0.0))) \
                .time(timestamp_now_kst, WritePrecision.NS) # 나노초 단위로 정밀도 변경

            self.write_api.write(bucket=config.INFLUX_WRITE_BUCKET, record=point)

        except Exception as e:
            print(f"❌ Failed to write inference results to InfluxDB: {e}")

    def write_state_change(self, user_id: str, new_state: str):
        """
        '수면 상태 변경' 이벤트만 별도의 '상태' Measurement에 기록합니다.
        """
        try:
            # ✨ [수정 2] ✨
            # new_state 문자열에서 timestamp를 찾지 않고, 현재 KST 시간을 직접 사용합니다.
            timestamp_now_kst = datetime.now(KST)
            
            # config.py에 정의된 상태 저장용 Measurement 이름 사용
            point = Point(config.INFLUX_STATE_MEASUREMENT) \
                .tag("state", new_state) \
                .field("value", 1)  \
                .time(timestamp_now_kst, WritePrecision.NS) # 나노초 단위로 정밀도 변경

            self.write_api.write(bucket=config.INFLUX_WRITE_BUCKET, record=point)

        except Exception as e:
            print(f"❌ Failed to write state change to InfluxDB: {e}")

    def close(self):
        """DB 클라이언트 연결을 종료합니다."""
        self.client.close()