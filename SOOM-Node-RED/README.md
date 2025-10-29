# SOOM-Voice · Node-RED Flows

음성 파이프라인(STT → Intent → API/MQTT → TTS)과 자동화 루틴, 수동 제어, LG ThinQ 연동을 처리하는 Node-RED 플로우 묶음입니다.  
구성 파일은 다음 네 개입니다.

- `voice_flow.txt` — 음성 이벤트/알림 파이프라인 (STT/Intent와 MQTT 브릿지)
- `routine_flow.txt` — 기상/수면 루틴 스케줄러 및 알람/권고 방송
- `mannual_flow.txt` — 수동(대시보드/HTTP) 제어 엔드포인트
- `Thinq_flow.txt` — LG ThinQ 연동(에어컨/조명/커튼 등) 어댑터

> 각 파일은 Node-RED의 **Import** 기능으로 그대로 붙여넣어 사용할 수 있는 JSON입니다. 확장자가 `.txt`라도 내용은 플로우 JSON입니다.

---

## 목차
1. [개요](#개요)
2. [사전 준비](#사전-준비)
3. [토픽 & 메시지 규격](#토픽--메시지-규격)
4. [빠른 시작](#빠른-시작)
5. [플로우별 상세](#플로우별-상세)
6. [테스트 시나리오](#테스트-시나리오)
7. [트러블슈팅](#트러블슈팅)
8. [라이선스](#라이선스)

---

## 개요

SOOM 시스템의 음성 명령을 처리하고 각종 가전/루틴을 실행하는 **Node-RED 백엔드**입니다.  
Python 기반 파이프라인에서 전달된 Intent 결과를 MQTT로 수신하여,  
LG ThinQ API 및 각 디바이스 노드로 연결하는 브릿지 역할을 수행합니다.

---

## 사전 준비

### 요구사항
- Node-RED ≥ 3.x
- MQTT 브로커 (예: Mosquitto)
- Python 음성 파이프라인 (SOOM-Voice)
- LG ThinQ 계정 및 토큰

---

## 토픽 & 메시지 규격

### MQTT 토픽

| 방향 | 토픽 | 설명 |
|------|------|------|
| Python → Node-RED | `/voice/command` | 음성 명령(Intent 결과) |
| Node-RED → Python | `/voice/alarm` | 알람 트리거 |
| Node-RED → Python | `/voice/sleep` | 권장 수면 시간 안내 |
| Node-RED → Python | `/voice/alert` | 일반 알림 |

### 메시지 예시

```json
{
  "device_type": "air_conditioner",
  "payload": {
    "ac_power": "ON",
    "target_ac_mode": "COOL",
    "target_ac_temperature": 22
  }
}

```

## 빠른 시작

1. Node-RED 실행 → Import → `voice_flow.txt` 붙여넣기 → Deploy  
2. 같은 방식으로 `routine_flow.txt`, `mannual_flow.txt`, `Thinq_flow.txt` Import  
3. MQTT 브로커 설정을 `MQTT_HOST`, `MQTT_PORT`로 맞추기  
4. Deploy 후 다음 명령으로 테스트:

```bash
mosquitto_pub -h localhost -t /voice/alarm -m '{}'
mosquitto_pub -h localhost -t /voice/sleep -m '{"sleep_time":"23:00"}'
```

---

## 플로우별 상세

### 🔹 voice_flow — 음성 이벤트 파이프라인

- Python 파이프라인 → MQTT `/voice/command` 수신  
- 명령 분석 후 디바이스 토픽(`/device/*/cmd`) 또는 알림(`/voice/alert`) 발행  
- `ENDPOINT`로 로그 업로드 가능

### 🔹 routine_flow — 루틴 스케줄러

- “내일 7시에 깨워줘” 명령 시 알람 예약  
- `cron-plus` 노드로 `/voice/alarm` 발행  
- 수면 권고(`/voice/sleep`) 자동 발행

### 🔹 mannual_flow — 수동 제어

- Dashboard나 HTTP로 장치 직접 제어  
- 조명/에어컨/커튼 수동 제어 지원

### 🔹 Thinq_flow — LG ThinQ 연동

- 표준 페이로드 → ThinQ API 변환  
- 전원/모드/온도 제어  
- 성공/오류를 `/device/<type>/ack`로 피드백

---

## 트러블슈팅

- **온도 설정 오류** → 모드(COOL/HEAT) 지정 필요  
- **ThinQ 오류(401/403)** → 토큰 만료 또는 지역 코드 불일치  
- **MQTT 연결 실패** → 브로커 설정 확인(`MQTT_HOST`, `MQTT_PORT`)  

---

## 라이선스

이 플로우 세트는 **MIT License** 하에 배포됩니다.  
LG ThinQ API는 LG전자(주)의 상표이며, 본 프로젝트는 비공식 예시를 포함합니다.
