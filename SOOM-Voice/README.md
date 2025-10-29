# SOOM‑Voice (2‑Stage Voice Pipeline)
**AI 음성 인터랙션으로 수면 루틴·스마트홈을 제어하는 온디바이스 파이프라인**  
**구성:** Silero‑VAD → Faster‑Whisper(STT) → Intent Parser → (MQTT/HTTP) → Node‑RED/LG ThinQ → KittenTTS(gTTS 대체 가능)

---

## 목차
1. [개요](#개요)  
2. [아키텍처](#아키텍처)  
3. [주요 기능](#주요-기능)  
4. [설치](#설치)  
5. [환경 변수](#환경-변수)  
6. [실행](#실행)  
7. [명령어 예시](#명령어-예시)  
8. [MQTT/Node-RED 연동](#mqttnode-red-연동)  
9. [파일 구조](#파일-구조)  
10. [트러블슈팅](#트러블슈팅)  
11. [라이선스](#라이선스)

---

## 개요
- 네트워크 불안정해도 동작하는 **로컬 온디바이스** 음성 파이프라인
- 2단계 대화형 흐름: **1) Wake word 감지 → 2) 명령어 인식**
- 스마트조명·에어컨·공청기·커튼, **알람/기상 루틴**까지 하나로 제어

---

## 아키텍처
```
[Mic] → [Silero‑VAD + WebRTC VAD] → [Faster‑Whisper(STT)]
       → [intent_recognize] → [HTTP/MQTT → Node‑RED → LG ThinQ]
       → [KittenTTS (or gTTS) TTS 출력]
```

**상태머신**
- `IDLE` → (Wake word) → `WAKE_PROCESSING` → (TTS 응답) → `LISTENING`
→ (명령 파싱) → `COMMAND_PROCESSING` → (TTS 응답) → `IDLE`

**TTS 잔향 차단**
- `gate.TTS_PLAYING` 이벤트 + `LAST_TTS_TS`/`REFRACTORY_SEC`로 STT 누화 차단

---

## 주요 기능
- **STT**: `faster-whisper` (ko/en), 저지연 파라미터 적용
- **VAD**: WebRTC VAD + 소프트 노이즈게이트, 잔향 차단 강화
- **Intent**: 시간/온도/모드/밝기/색온도/커튼 등 파라미터 파싱 최적화
- **TTS**: 기본 `KittenTTS`(24kHz, sounddevice 출력). 알림/알람은 `playsound`로 mp3 재생
- **MQTT/HTTP**: Node‑RED/ThinQ API 연동, 재시도 로직 포함

---

## 설치
```bash
git clone <this-repo>
cd SOOM-Voice

# 필수 패키지
pip install faster-whisper webrtcvad sounddevice soundfile numpy paho-mqtt requests python-dotenv kittentts playsound==1.2.2

---

## 실행
### 일반 모드
```bash
python pipeline.py
```
- 최초에 API 연결 테스트 진행 → 성공 시 TTS 모델 로딩 → **Wake word 대기**
- Wake word(예: “헤이 숨”, “숨”) 말한 뒤, TTS 응답이 끝나면 **명령어** 말하기

---

## 명령어 예시
| 발화 | 파싱 결과(요지) | 동작 |
|---|---|---|
| “헤이 숨” | wake_word | 2단계 진입(TTS 응답 후 명령 대기) |
| “에어컨 켜줘” | `device=air_conditioner, power=on` | AC 전원 ON |
| “에어컨 24도로” | `device=air_conditioner, temp=24` | (모드 확인 필요) 온도 설정 |
| “냉방으로 바꿔” | `device=air_conditioner, mode=cool` | 모드 설정 |
| “조명 3단계” | `device=smart_light, brightness=75` | 밝기 75% |
| “전구색으로” | `device=smart_light, cct=3000K` | 색온도 3000K |
| “커튼 열어줘” | `device=smart_curtain, power=on` | 커튼 열기 |
| “내일 7시에 깨워줘” | `category=routine_setting, time=07:00, offset=+1d` | 알람 설정 |
| “10분만” | `snooze` | 스누즈 +10분 |

> **에어컨 온도 설정**은 **현재 모드(COOL/HEAT/AUTO)** 의존 → 모드 없으면 Node‑RED에서 가드 권장.

---

## MQTT/Node-RED 연동
### 구독/발행 토픽
- 구독(파이프라인):  
  - `/voice/alarm` → `ALARM_SOUND` 재생  
  - `/voice/alert` → `ALERT_SOUND` 재생  
  - `/voice/sleep` → `{"sleep_time":"23:00"}` 형식 수신 시 “Recommended sleep time is 11:00 PM.” TTS  
  - `/voice/time`  → 동형식 처리
- 발행(백엔드에서 필요 시): 없음 (본 파이프라인은 HTTP로 API 전송)

### ThinQ 제어 바디 예시(Node‑RED Function 결과)
```jsonc
// 전원
{"operation":{"airConOperationMode":"POWER_ON"}}  // or POWER_OFF

// 모드
{"airConJobMode":{"currentJobMode":"COOL"}}       // COOL | HEAT | AUTO | AIR_DRY

// 온도 (모드별 키)
{"temperature":{"coolTargetTemperature":22,"unit":"C"}}
{"temperature":{"heatTargetTemperature":24,"unit":"C"}}
```

---

## 파일 구조
```plaintext
SOOM-Voice
├── gate.py
├── intent_recognize.py
├── pipeline.py
├── stt_whisper.py
├── tts_kitten.py
├── assets/
│   ├── alert.mp3
│   └── wake.mp3
```
- **gate.py**: TTS 상태 이벤트(`TTS_PLAYING`), 잔향 차단 타이밍(`LAST_TTS_TS`, `REFRACTORY_SEC`)
- **intent_recognize.py**: Wake word/명령 파싱, 디바이스/모드/밝기/시간 등 규칙 기반 파서
- **pipeline.py**: 2단계 상태머신, MQTT/HTTP 연동, 알림 사운드 재생, 통계
- **stt_whisper.py**: 마이크 입력 + WebRTC VAD 세그먼터 + Faster‑Whisper STT
- **tts_kitten.py**: KittenTTS 합성/캐시/출력, 전역 헬퍼(`speak_*`)

---

## 트러블슈팅
- **알림 소리(playsound) 재생 실패(Windows)**  
  - 경로/한글/공백 회피를 위해 `pipeline._play_sound()`에서 **임시 안전경로로 복사 후 재생** 처리됨.  
  - 여전히 오류면 `ALARM_SOUND/ALERT_SOUND` 절대경로로 설정.
- **마이크 무음/지연**  
  - `SD_INPUT_DEV` 장치 인덱스 지정, `AMP_DB`로 프리앰프 조정, `VAD_MODE`=2~3 시도.
- **Whisper 추론 느림**  
  - `WHISPER_MODEL=tiny/base`, `BEAM_SIZE=1`, `BEST_OF=1`, `COMPUTE=int8` 유지. CUDA 가능 시 `WHISPER_DEVICE=cuda`.

---

## 라이선스
- 본 저장소: MIT License  
- 외부 OSS(Whisper, Silero‑VAD, KittenTTS, webrtcvad 등) 라이선스 준수
