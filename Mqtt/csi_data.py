import json, os
from paho.mqtt.client import Client
from influxdb_client import InfluxDBClient, Point, WritePrecision
from dotenv import load_dotenv
from datetime import timedelta, timezone, datetime
from queue import Queue
import threading

# .env 로드
load_dotenv()

# 큐 생성
data_queue = Queue()

# MQTT 설정
MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_PORT = int(os.getenv("MQTT_PORT"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC")

# InfluxDB 설정
INFLUXDB_URL = os.getenv("INFLUXDB_URL")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET")

# InfluxDB 클라이언트 생성
influx_client = InfluxDBClient(
    url=INFLUXDB_URL,
    token=INFLUXDB_TOKEN,
    org=INFLUXDB_ORG
)
write_api = influx_client.write_api()


# MQTT 메시지 수신 → 큐에 저장
def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        topic = msg.topic
        data_queue.put((topic, payload))  # 큐에 저장
    except Exception as e:
        print("error:", e)


def influx_worker():
    kst = timezone(timedelta(hours=9))
    while True:
        topic, payload = data_queue.get()
        try:
            now_kst = datetime.now(kst)
            point = None
            if topic == "sensor/csi_measurement":
                point = (
                    Point("csi_measurement")
                    .field("real_timestamp", str(payload["real_timestamp"]))  # 정밀 타임스탬프
                    .field("data", str(payload["data"]))  # 문자열: CSI 데이터
                    .time(now_kst, WritePrecision.MS))  # 기록 시각: 밀리초 정밀도

            if point:
                write_api.write(bucket=INFLUXDB_BUCKET, record=point)
                print(f"[{topic}] save success")

        except Exception as e:
            print("DB save error:", e)
        finally:
            data_queue.task_done()


# 워커 스레드 실행
threading.Thread(target=influx_worker, daemon=True).start()

# MQTT 클라이언트 설정 및 시작
mqtt_client = Client(client_id="mqtt_csi_listener")
mqtt_client.on_message = on_message
mqtt_client.connect(MQTT_BROKER, MQTT_PORT)
mqtt_client.subscribe(MQTT_TOPIC)

print("MQTT listening... Ctrl+C to exit")
mqtt_client.loop_forever()
