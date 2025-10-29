# SOOM
> 🛌  SOOM, get SMART &amp; RESTFUL Sleep.

**Sleep Observation & Optimization Module**   

---
### Quick Links  
- **[SOOM-FE.dashboard](./SOOM-FE.dashboard/README.md)** — Frontend 대시보드
- **[SOOM-BE.platform](./SOOM-BE.platform/README.md)** — Backend 플랫폼 
- **[SOOM-Voice](./SOOM-Voice/README.md)** — 온디바이스 음성 파이프라인 
- **[SOOM-Node-RED](./SOOM-Node-RED/README.md)** — 자동화/음성/ThinQ 플로우
- **[SOOM-AI](./SOOM-AI/README.md)** - AI 모델 초기 학습, 데이터 전처리 및 시각화 등 핵심 코드 저장소
- **[SOOM-AI.OnDevice](./SOOM-AI.OnDevice/README.md)** - 메인 추론 파이프라인  
- **[SOOM-AI.fine_tuning](./SOOM-AI.fine_tuning/README.md)** — 미세조정(Fine-tuning) 코드  
- **[SOOM-EM.devices](./SOOM-EM.devices/README.md)** — ESP32 임베디드 제어 모듈

---

### 목차
1. [개요](#개요)  
2. [시스템 아키텍처](#시스템-아키텍처)  
3. [프로젝트 구조](#프로젝트-구조)  
4. [모듈 & 기능](#모듈--기능)  
5. [실행](#실행)  
6. [라이선스](#라이선스)

---

### 개요
SOOM은 **비접촉 수면 감지**와 **스마트홈 제어/자동화**를 결합한 플랫폼입니다.  
- **관찰(Observation)**: 실내 환경·수면 신호를 수집하고 시각화  
- **최적화(Optimization)**: 루틴·음성·AI 분석으로 수면 환경 자동 조정  
- **통합 UX**: 대시보드에서 수면 리포트, 기기 제어, 자동화 설정을 한 번에

---

### 시스템 아키텍처
> **소프트웨어 아키텍쳐**  
> 대시보드, DB, AI 분석 모듈, 임베디드 디바이스, 음성 파이프라인 및 자동화 플로우(Node-RED) 로 구성된 **분산형 IoT-Edge 통합 구조**  
> 각 모듈은 독립적으로 배포 및 실행되며, MQTT·HTTP·WebSocket을 통해 실시간으로 상호 통신  
  <img width="850" height="455" alt="image" src="https://github.com/user-attachments/assets/5bccde91-3afa-4faa-bcd8-c4c098d187a4" />

<br>

> **하드웨어 아키텍쳐**  
> ESP32-C3/C6 모듈 (조명, 커튼, 공기청정기, 에어컨, CSI 수집)  
> 센서: DHT22, PMS7003, MQ135, CSI(OFDM Subcarrier)  
> 게이트웨이: Raspberry Pi 4 + webOS OSE  
  <img width="713" height="594" alt="image" src="https://github.com/user-attachments/assets/c1b93699-cfa0-46da-9587-508417ad9461" />

---

### 프로젝트 구조
```
SOOM/
├─ SOOM-FE.dashboard/     # webOS 대시보드 (Enact/React, Vite)
├─ SOOM-BE.platform/      # FastAPI 백엔드 (MariaDB/InfluxDB/MQTT)
├─ SOOM-Voice/            # 온디바이스 음성 파이프라인 (VAD→STT→Intent→TTS)
├─ SOOM-Node-RED/         # Node-RED 플로우 (voice/routine/manual/ThinQ)
├─ SOOM-AI/               # 수면·호흡 분석, 학습/추론, 신호 전처리·증강
├─ SOOM-AI.OnDevice/      # 학습된 모델을 임베디드 환경에 배포 및 실행하기 위한 메인 추론 파이프라인
├─ SOOM-AI.fine_tuning/   # 성능 최적화 및 특정 작업 적응을 위한 미세조정 코드
├─ SOOM-EM.devices/       # ESP32 장치별 펌웨어 (aircon/light/curtain/CSI 등)
└─ README.md              # 현재 파일
```
---
### 모듈 & 기능
**1. SOOM-FE.dashboard** (Enact/React + webOS)
- 실내 환경 모니터링: 온도·습도·공기질·미세먼지 실시간 표시 (WebSocket)
- 수면 리포트: 점수·수면시간·뒤척임·호흡 시각화 (REST)
- 스마트홈 제어: 조명·커튼·에어컨·공기청정기 제어
- 자동화 루틴 설정: 기상/취침 조건 기반 실행 루틴 설정 (예: 조명 끄기 + 커튼 닫기)
- 빌드/배포: Vite → webOS IPK

**2. SOOM-BE.platform** (FastAPI)
- API: 대시보드·루틴·디바이스 제어·수면 데이터 제공
- DB: MariaDB(사용자/루틴), InfluxDB(시계열/센서)
- MQTT: ESP32 센서·제어, CSI 수집
- 실행: `uvicorn main:app --host 0.0.0.0 --port 8000`

**3. SOOM-Voice** (온디바이스 2-Stage)
- 파이프라인: Silero-VAD → Faster-Whisper(STT) → Intent → API/MQTT → TTS
- 명령: 조명·에어컨·커튼 제어, 알람·루틴 설정, 알림 방송
- 연동: Node-RED 플로우 및 LG ThinQ 어댑터

**4. SOOM-Node-RED**
- `voice_flow`, `routine_flow`, `mannual_flow`, `Thinq_flow`
- Node-RED Import → Deploy 후 즉시 사용 가능 (MQTT 표준 규격)

**5. SOOM-AI** (신호 처리 및 학습)
- utils: FFT/DWT/Kalman/PCA/정규화/CSI 추출/호흡수 계산
- augmentation: 데이터 증강 및 시각화
- model: 1D-CNN 학습·평가·저장, TFLite 변환
- script: 전처리 및 분석용 스크립트

**6. SOOM-EM.devices** (ESP32)
- 모듈: smart_light, smart_curtain, air_purifier, air_conditioner, wifi_csi_{recv,send}, csi_saver
- 설정: `idf.py menuconfig` → Wi-Fi/MQTT/GPIO/주기 지정
- MQTT 규격:  
  - 명령 → `sensor/<device>/cmd`  
  - 상태 → `sensor/<device>`

---

## 실행

### 공통 요구 사항
- Node.js 18+ / npm  
- Python 3.10+ / 가상환경  
- FastAPI, MariaDB, InfluxDB, Mosquitto(MQTT)  
- webOS OSE (RPi4) + ares-cli (IPK 배포 시)  

### Backend
```bash
cd SOOM-BE.platform
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Frontend
```
cd SOOM-FE.dashboard
npm install
npm run dev           # 개발
npm run build         # dist 생성
# webOS 배포
ares-package ./dist && ares-install *.ipk
```

### Voice Pipeline
```
cd SOOM-Voice
pip install -r requirements.txt
python pipeline.py
```

### Node-RED Flows
- Node-RED 실행 → Import → 각 .txt 파일 붙여넣기 → Deploy

### EM.devices
```
idf.py set-target esp32c3
idf.py menuconfig
idf.py build flash monitor
```
---

### 라이선스
- 코드: MIT (모듈별 LICENSE 참고)
- LG ThinQ는 LG전자의 상표이며, 본 프로젝트는 비공식 예시를 포함합니다.

⸻

© 2025 SOOM. All rights reserved.
Sleep better with SOOM 🌙
