from fastapi import APIRouter
import os
import dotenv
import paho.mqtt.client as mqtt
import json
from starlette.responses import JSONResponse
from schemas.control import DeviceControl
from util.util import get_latest_values

dotenv.load_dotenv()

router = APIRouter(prefix="/api/v1/device", tags=["device"])

MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_PORT   = int(os.getenv("MQTT_PORT"))

mqtt_client = mqtt.Client()


mqtt_client.reconnect_delay_set(min_delay=1, max_delay=60)

mqtt_client.connect_async(MQTT_BROKER, MQTT_PORT, keepalive=60)
mqtt_client.loop_start()

@router.post("/control")
async def control_device(device: DeviceControl):
    topic = f"sensor/{device.device_type}/cmd"
    payload = json.dumps(device.payload)

    if not mqtt_client.is_connected():
        try:
            mqtt_client.reconnect()
        except Exception:
            return JSONResponse(status_code=503, content="mqtt not connected")
    print(topic, payload)
    mqtt_client.publish(topic, payload)
    return JSONResponse(status_code=200, content="success")

@router.post("/sensor", response_model=dict)
async def send_sensor() :
    data = get_latest_values()

    return data