import json, os
from paho.mqtt.client import Client, MQTTv311
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

# MQTT 연결 콜백
def on_connect(client, userdata, flags, rc):

    client.subscribe(MQTT_TOPIC)


# MQTT 메시지 수신 → 큐에 저장
def on_message(client, userdata, msg):
    print(f"connect: {msg.topic}")
    try:
        payload = json.loads(msg.payload.decode())
        print(payload)
        topic = msg.topic
        data_queue.put((topic, payload))  # 큐에 저장
    except Exception as e:
        print("error:", e)

# InfluxDB 저장
def influx_worker():
    kst = timezone(timedelta(hours=9))
    while True:
        topic, payload = data_queue.get()
        try:
            now_kst = datetime.now(kst)
            point = None

            if topic == "sensor/aircondition":
                point = (
                    Point("aircondition_sensor")
                    .field("power", str(payload['power']))
                    .field("temperature", float(payload['temperature']))
                    .field("humidity", float(payload['humidity']))
                    .field("mode", str(payload['mode']))
                    .time(now_kst, WritePrecision.S)
                )

            elif topic == "sensor/air_purifier":
                point = (
                    Point("air_purifier_sensor")
                    .field("power", str(payload['power']))
                    .field("pm_2_5", float(payload['pm_2_5']))
                    .field("pm_10", float(payload['pm_10']))
                    .field("aqi", int(payload['aqi']))
                    .field("mode", str(payload['mode']))
                    .time(now_kst, WritePrecision.S)
                )

            elif topic == "sensor/smart_curtain":
                point = (
                    Point("smart_curtain")
                    .field("power", str(payload['power']))
                    .time(now_kst, WritePrecision.S)
                )

            elif topic == "sensor/smart_light":
                point = (
                    Point("smart_light")
                    .field("power", str(payload['power']))
                    .field("illuminance", int(payload['illuminance']))
                    .field("light_level", float(payload['light_level']))
                    .time(now_kst, WritePrecision.S)
                )

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
mqtt_client = Client(client_id="mqtt_env_listener", protocol=MQTTv311)
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
mqtt_client.connect(MQTT_BROKER, MQTT_PORT)

print("MQTT listening... Ctrl+C to exit")
mqtt_client.loop_forever()
