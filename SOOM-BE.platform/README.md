# SOOM-BE.platform

SOOM 백엔드 플랫폼입니다.  
FastAPI를 기반으로 하며, 사용자 루틴 관리, 수면 데이터 수집, MQTT 통신 등 다양한 기능을 제공합니다.

---

## 폴더 구조

```
SOOM-BE.platform/                     
├── Models/                    # 데이터베이스 모델
│   ├── log.py                 # 사용자 행동 로그 또는 시스템 로그 모델 
│   ├── routine.py             # 사용자 루틴(수면/기상/외출 등) 정보 모델
│   ├── sleepdashboard.py      # 수면 분석 대시보드 관련 데이터 모델
│   └── user.py                # 사용자 수면, 기상, 예측값 관련 모델
│
├── Mqtt/                      # MQTT 관련 모듈
│   ├── connect.py             # 센서 데이터 mqtt 토픽 구독 및 InfluxDB 저장 로직
│   └── csi_data.py            # 수신된 CSI(Channel State Information) InfluxDB 저장 로직 
│
├── routers/                   # FastAPI 라우터
│   ├── dashboard.py           # 대시보드 관련 API (수면 통계, 시각화 등)
│   ├── device.py              # 디바이스 제어 명령 API
│   ├── routine.py             # 사용자 루틴 관련 (등록, 조회, 수정), 제어로그 API
│   └── user.py                # 사용자 하루 수면, 기상, 예측값 관련 API
│
├── schemas/                   # Pydantic 스키마
│   ├── control.py             # 디바이스 제어 요청 스키마
│   ├── log.py                 # 로그 저장 스키마
│   ├── routine.py             # 루틴 생성 및 업업데이트 스키마
│   ├── sleepdata.py           # 수면 리포트 베이스 스키마
│   └── user.py                # 사용자 수면, 기상, 예측값 (등록, 조회, 수정 등) 관련 스키마
│
├── util/                      # 유틸리티 함수
│   └── util.py                # 전역 함수
│
│── database.py                # DB 설정
│── main.py                    # fastapi 실행  
│── requirements.txt           # 필수 라이브러리 목록
```

---
# 실행 방법


## 1. 가상환경 설정
python -m venv .venv  
source .venv/bin/activate  # (Windows: .venv\Scripts\activate)  

## 2. 패키지 설치
pip install -r requirements.txt  

## 3. 환경변수 설정 (.env 파일 생성)

### MQTT 설정  
MQTT_BROKER=broker_url  
MQTT_PORT=broker_port        #기본: 1883  
MQTT_TOPIC=sensor_topic      #센서 데이터가 게시되는 토픽명명

### InfluxDB 설정  
INFLUXDB_URL=InfluxDB_url  
INFLUXDB_TOKEN=InfluxDB_Token  
INFLUXDB_ORG=InfluxDB_ORG  
INFLUXDB_BUCKET=InfluxDB_Bucket  

### MariaDB 설정  
DB_USER=MariaDB_User  
DB_PASSWORD=MariaDB_Password  
DB_HOST=MariaDB_Host  
DB_PORT=MariaDB_Port  
DB_NAME=MariaDB_Database_Name  
  
### 4. 서버 실행  
4.1 FastAPI 서버 실행  
source venv/bin/activate  
uvicorn main:app --host 0.0.0.0 --port 8000  


4.2 Mqtt 활성화  
cd Mqtt  
python3 connect.py  


---
# 주요 기능  

✅ 사용자 수면 리포트, 측정된 수면 데이터 저장  

✅ 수면 루틴 저장 및 조회  

✅ 수면 대시보드 API 제공  

✅ MQTT 실시간 데이터 저장 및 프론트엔드 제공  

✅ RESTful API 설계  



---
# 기술 스택

FastAPI - Python 웹 프레임워크

SQLAlchemy - ORM

Pydantic - 데이터 검증 및 직렬화

paho-mqtt - MQTT 프로토콜 처리

Uvicorn - ASGI 서버

MariaDB - 관계형 데이터베이스, 사용자 및 루틴 정보 저장에 사용

InfluxDB - 시계열 데이터 저장 (수면 데이터, 센서 데이터, CSI 라벨 등)

Mosquitto (MQTT Broker) - 경량 메시지 브로커, ESP 디바이스 데이터 송수신 처리


## 아키텍처 구성 요약

```
        ┌────────────┐
        │  ESP32     │  ← 센서 데이터 측정
        └────┬───────┘
             │ MQTT Publish
             ▼
     ┌────────────────┐
     │ Mosquitto MQTT │  ← 브로커
     └────┬────┬──────┘
          │    │
          │    └─────▶ FastAPI ←────────────┐
          │             (paho-mqtt)          │
          ▼                                  │ REST API 호출
    ┌────────────┐                           │
    │ InfluxDB   │  ← 수면/센서 시계열 저장   │
    └────────────┘                           │
                                             ▼
                                    ┌──────────────┐
                                    │ MariaDB      │ ← 사용자 정보, 루틴 저장
                                    └────┬─────────┘
                                         │
                      ┌──────────────────┘
                      │
             ┌────────▼────────┐
             │   Node-RED      │ ← 루틴 실행 및 DB 제어
             └──────┬──────────┘
                    │
                    ▼
             ┌────────────┐
             │  IoT 제어   │  ← 가전 기기 제어 (MQTT Publish)
             └────┬───────┘
                  ▲
     ┌────────────┴────────────┐
     │   사용자 대시보드 (FE)   │ ← 제어 명령, 루틴 설정 등
     └─────────────────────────┘
```

---

## 흐름 요약

- **ESP32**가 측정한 센서 데이터는 MQTT로 전송되어 **InfluxDB**에 저장됩니다.
- **Node-RED**는 사용자가 설정한 **루틴**을 실행하고, 관련 데이터는 **MariaDB**에 저장됩니다.
- 사용자가 **프론트엔드 대시보드**에서 기기를 제어 시, FastAPI가 MQTT를 통해 **ESP32 디바이스를 제어**합니다.
- 사용자가 **프론트앤드 대시보드**에서 수면리포트를 조회하면, FastAPI가 influxDB에 있는 데이터를 기반으로 수면리포트를 생성합니다.
- 시스템은 **센서 수집 ↔ 저장 ↔ 루틴 실행 ↔ 사용자 제어**의 완전한 데이터 흐름을 가집니다.

---


📄 API 문서

http://{라즈베리파이IP주소}:8000/docs
FastAPI의 자동 생성 Swagger UI에서 모든 엔드포인트 확인 가능
