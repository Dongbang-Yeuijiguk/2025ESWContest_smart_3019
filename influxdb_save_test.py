from influxdb_client import InfluxDBClient, Point, WritePrecision
from datetime import datetime, timezone

# ===== 설정 =====
INFLUX_URL    = "http://localhost:8086"
INFLUX_TOKEN  = "soom-token-123"     # 네 토큰으로 변경
INFLUX_ORG    = "soom-org"
INFLUX_BUCKET = "soom-bucket"

# ===== 클라이언트 생성 =====
client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
write_api = client.write_api()

# ===== 테스트 데이터 포인트 =====
point = (
    Point("test_measurement")
    .tag("device", "debug")
    .field("value", 123.45)
    .time(datetime.now(timezone.utc), WritePrecision.S)
)

# ===== InfluxDB에 기록 =====
write_api.write(bucket=INFLUX_BUCKET, record=point)
print("✅ Test data written to InfluxDB.")

client.close()
