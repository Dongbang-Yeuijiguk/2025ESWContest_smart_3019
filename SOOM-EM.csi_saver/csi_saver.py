import serial
import pytz
from datetime import datetime
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

INFLUX_URL = "http://localhost:8086"
INFLUX_TOKEN = "YOUR_INFLUX_TOKEN"
INFLUX_ORG = "YOUR_ORG"
INFLUX_BUCKET = "YOUR_BUCKET"

SERIAL_PORT = "/dev/ttyAMA2"
BAUD_RATE = 115200

KST = pytz.timezone('Asia/Seoul')

def main():
    print(f"Attempting to connect to InfluxDB: {INFLUX_URL}")
    try:
        client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
        write_api = client.write_api(write_options=SYNCHRONOUS)
        
        # InfluxDB 연결 확인
        if not client.ping():
            print("InfluxDB connection failed. Check your settings (URL, Token).")
            return
        print("InfluxDB connection successful.")
        
    except Exception as e:
        print(f"InfluxDB client initialization error: {e}")
        return

    ser = None
    try:
        print(f"Attempt to open serial port: {SERIAL_PORT} (Baud: {BAUD_RATE})")
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print("Serial port connection successful. Waiting for data to be received...")

        while True:
            try:
                line_bytes = ser.readline()
                if not line_bytes:
                    continue

                line = line_bytes.decode('utf-8').strip()

                if not line:
                    continue

                parts = line.split(',', 1)
                
                if len(parts) == 2:
                    esp_timestamp_str = parts[0]
                    csi_data_str = parts[1].strip('"')
                    
                    payload = {
                        "real_timestamp": esp_timestamp_str,
                        "data": csi_data_str
                    }
                    
                    now_kst = datetime.now(KST)

                    point = Point("csi_measurement") \
                        .field("real_timestamp", str(payload["real_timestamp"])) \
                        .field("data", str(payload["data"])) \
                        .time(now_kst, WritePrecision.MS)

                    write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)
                    
                    print(f"[{now_kst.strftime('%Y-%m-%d %H:%M:%S')}] Data storage success: TS={esp_timestamp_str}")

                else:
                    print(f"Data format error (ignored): {line}")

            except UnicodeDecodeError:
                print("Serial data decoding error. (Ignored)")
            except Exception as e:
                print(f"An error occurred while processing data: {e}")
                
    except serial.SerialException as e:
        print(f"Serial port error: {e}")
        print(f"'{SERIAL_PORT}'Make sure it is the correct port and has permissions.")
    except KeyboardInterrupt:
        print("\nRequest to stop script (Ctrl+C).")
    finally:
        # 리소스 정리
        if ser and ser.is_open:
            ser.close()
            print("시리얼 포트 닫힘.")
        if 'client' in locals():
            client.close()
            print("InfluxDB client closed.")

if __name__ == "__main__":
    main()