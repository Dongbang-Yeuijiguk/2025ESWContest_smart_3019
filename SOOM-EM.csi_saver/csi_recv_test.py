import serial
import time

# ===== 설정 =====
SERIAL_PORT = "/dev/ttyACM2"   # ESP32가 연결된 포트
BAUDRATE    = 3000000          # ESP32 코드의 설정과 동일하게
TIMEOUT     = 0.5              # 0.5초마다 깨어나서 Ctrl+C 체크 가능

# ===== 실행 =====
try:
    ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=TIMEOUT)
    print(f"[INFO] Serial opened: {SERIAL_PORT} @ {BAUDRATE}")

    while True:
        line = ser.readline()
        if not line:
            continue
        try:
            decoded = line.decode("utf-8", errors="ignore").strip()
        except Exception:
            continue

        if "CSI_DATA" in decoded:
            print(decoded)  # 전체 줄 출력
        # else:
        #     pass  # 필요하면 필터링 제거해서 전체 출력 가능

except serial.SerialException as e:
    print(f"[ERROR] 시리얼 포트 열기 실패: {e}")

except KeyboardInterrupt:
    print("\n[INFO] 사용자 종료 요청 (Ctrl+C)")

finally:
    try:
        ser.close()
        print("[INFO] Serial closed.")
    except Exception:
        pass
