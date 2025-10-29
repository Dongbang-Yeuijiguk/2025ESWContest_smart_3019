# pipeline.py
# 2단계 대화형 음성 인식 시스템: Wake word → TTS 응답 → 명령어 → API 전송 → TTS 응답
import json
import time
import requests
import threading
from typing import Dict, Any, Optional
from enum import Enum
import os
import paho.mqtt.client as mqtt
import stt_whisper
import intent_recognize
from tts_kitten import speak_wake_word_response, speak_timeout_message, speak_intent_result, get_tts_instance
from gate import TTS_PLAYING, LAST_TTS_TS, REFRACTORY_SEC
import time as _t

from dotenv import load_dotenv
load_dotenv()

MQTT_HOST=os.getenv('MQTT_HOST')
MQTT_PORT=1883
MQTT_TOPIC_NOTIFY= "/voice/alert"
ALERT_TEXT = "Dangerous! Dangerous! Wake up!                  a"

INBOUND_API_HOST = "0.0.0.0"
INBOUND_API_PORT = 8099
INBOUND_API_TOKEN = os.getenv("VOICE_PIPELINE_TOKEN", "changeme")

API_ENDPOINT = os.getenv("ENDPOINT")
REQUEST_TIMEOUT = 5

MAX_RETRIES = 3

class PipelineState(Enum):
    """파이프라인 상태"""
    IDLE = "idle"                    # 대기 상태 (wake word 감지 대기)
    WAKE_PROCESSING = "wake_processing"  # Wake word 처리 중
    LISTENING = "listening"          # 명령어 대기 상태 (wake word 후)
    COMMAND_PROCESSING = "command_processing"  # 명령 처리 중
    TTS_PLAYING = "tts_playing"      # TTS 재생 중

class VoicePipeline:
    """2단계 대화형 음성 인식 파이프라인"""

    def _start_mqtt(self):
        client = mqtt.Client()
        def on_connect(c, u, f, rc):
            if self.debug: print(f"[MQTT] connect rc={rc} -> subscribe {MQTT_TOPIC_NOTIFY}")
            c.subscribe(MQTT_TOPIC_NOTIFY, qos=1)

        def on_message(c, u, msg):
            if self.debug: print(f"[MQTT] {msg.topic}: {msg.payload[:120]!r}")
            # 경보는 바로 말한다 (재생 중이면 끊고)
            if TTS_PLAYING.is_set():
                try: self.tts.stop()
                except: pass
            intent = {
                "success": True,
                "category": "alarm",
                "confidence": 1.0,
                "command": "ALERT",
                "say": ALERT_TEXT,            # 혹시 이 키를 쓰는 구현 대비
                "tts_text": ALERT_TEXT,       # 혹시 이 키를 쓰는 구현 대비
                "response_text": ALERT_TEXT,  # 일반 케이스
                "message": ALERT_TEXT         # 백업
            }
            speak_intent_result(intent, callback=self._on_command_complete)

        client.on_connect = on_connect
        client.on_message = on_message
        client.connect_async(MQTT_HOST, MQTT_PORT, keepalive=30)
        client.loop_start()
        self.mqtt = client  # 참조 유지

    def __init__(self, 
                 api_endpoint: str = API_ENDPOINT,
                 command_timeout: float = 10.0,  # 명령어 대기 시간
                 wake_word_confidence_threshold: float = 0.7,  # Wake word 신뢰도 임계값
                 command_confidence_threshold: float = 0.6,    # 명령어 신뢰도 임계값
                 debug: bool = True):
        self.api_endpoint = api_endpoint
        self.debug = debug
        self.command_timeout = command_timeout
        self.wake_word_confidence_threshold = wake_word_confidence_threshold
        self.command_confidence_threshold = command_confidence_threshold
        
        # 상태 관리
        self.state = PipelineState.IDLE
        self.state_lock = threading.Lock()
        self.command_timer: Optional[threading.Timer] = None
        
        # TTS 인스턴스
        self.tts = get_tts_instance()
        
        # 통계
        self.stats = {
            'total_stt_received': 0,
            'wake_word_attempts': 0,
            'wake_word_success': 0,
            'command_attempts': 0,
            'command_success': 0,
            'api_success': 0,
            'api_failed': 0,
            'timeouts': 0,
            'state_transitions': 0
        }
        
        # 마지막 처리 시간 기록
        self.last_wake_word_time = 0.0
        self.last_command_time = 0.0

    def process_stt_result(self, text: str):
        """STT 결과 처리 콜백 - 상태에 따라 다르게 처리"""
        
        # TTS 재생 중이면 무시 (하드 블록)
        if TTS_PLAYING.is_set():
            if self.debug:
                print("[PIPELINE] 🔇 TTS 재생 중 → STT 드롭")
            return
            
        # TTS 잔향 차단 (소프트 블록)
        if (_t.monotonic() - LAST_TTS_TS) < REFRACTORY_SEC:
            if self.debug:
                dt = _t.monotonic() - LAST_TTS_TS
                print(f"[PIPELINE] 🔕 잔향차단 {dt:.2f}s → 드롭")
            return

        if not text or not text.strip():
            return

        self.stats['total_stt_received'] += 1
        
        if self.debug:
            print(f"[PIPELINE] STT 수신 [{self.state.value}]: '{text}'")
        
        with self.state_lock:
            if self.state == PipelineState.IDLE:
                self._handle_wake_word_detection(text)
            elif self.state == PipelineState.LISTENING:
                self._handle_command_input(text)
            elif self.state in [PipelineState.WAKE_PROCESSING, 
                              PipelineState.COMMAND_PROCESSING, 
                              PipelineState.TTS_PLAYING]:
                if self.debug:
                    print(f"[PIPELINE] 🔄 처리 중 ({self.state.value}) → 입력 무시")

    def _handle_wake_word_detection(self, text: str):
        """Wake word 감지 처리 (1단계)"""
        self.stats['wake_word_attempts'] += 1
        
        if self.debug:
            print(f"[PIPELINE] 1단계: Wake word 체크 중...")
        
        # Wake word 전용 인식 사용
        wake_result = intent_recognize.intent_recognize_wake_word(text)
        
        if self.debug:
            print(f"[PIPELINE] Wake word 결과: {wake_result}")
        
        if (wake_result.get("success", False) and 
            wake_result.get("confidence", 0) >= self.wake_word_confidence_threshold):
            
            self.stats['wake_word_success'] += 1
            self.last_wake_word_time = time.time()
            self._transition_state(PipelineState.WAKE_PROCESSING)
            
            if self.debug:
                confidence = wake_result.get("confidence", 0)
                print(f"[PIPELINE] ✅ Wake word 감지! 신뢰도: {confidence:.2f}")
            
            # Wake word 응답 TTS
            speak_wake_word_response(callback=self._on_wake_response_complete)
        else:
            if self.debug:
                confidence = wake_result.get("confidence", 0)
                error = wake_result.get("error", "Unknown error")
                print(f"[PIPELINE] ❌ Wake word 미감지 (신뢰도: {confidence:.2f}, 오류: {error})")

    def _on_wake_response_complete(self, success: bool, text: str):
        """Wake word 응답 TTS 완료 후 콜백"""
        if self.debug:
            print(f"[PIPELINE] Wake word TTS 완료 (성공: {success})")
        
        if success:
            with self.state_lock:
                self._transition_state(PipelineState.LISTENING)
                if self.debug:
                    print("[PIPELINE] 🎤 2단계: 명령어 대기 모드 진입")
                
                # 타임아웃 타이머 설정
                self.command_timer = threading.Timer(
                    self.command_timeout, 
                    self._on_command_timeout
                )
                self.command_timer.start()
        else:
            # TTS 실패시 IDLE로 복귀
            with self.state_lock:
                self._transition_state(PipelineState.IDLE)
                if self.debug:
                    print("[PIPELINE] ❌ Wake word TTS 실패 → IDLE 복귀")

    def _handle_command_input(self, text: str):
        """명령어 입력 처리 (2단계)"""
        self.stats['command_attempts'] += 1
        
        if self.debug:
            print(f"[PIPELINE] 2단계: 명령어 처리 중...")
        
        # 타이머 취소
        if self.command_timer:
            self.command_timer.cancel()
            self.command_timer = None
        
        self._transition_state(PipelineState.COMMAND_PROCESSING)
        self.last_command_time = time.time()
        
        try:
            # Wake word 없이 명령어만 인식
            intent_result = intent_recognize.intent_recognize_command(text)
            
            if self.debug:
                print(f"[PIPELINE] 명령어 인식 결과: {intent_result}")

            if (intent_result.get("success", False) and 
                intent_result.get("confidence", 0) >= self.command_confidence_threshold):
                
                self.stats['command_success'] += 1
                
                # API 전송 먼저 (비동기)
                self._send_to_api(text, intent_result)
                
                # 성공 응답 TTS
                speak_intent_result(intent_result, callback=self._on_command_complete)
                
                if self.debug:
                    confidence = intent_result.get("confidence", 0)
                    category = intent_result.get("category", "unknown")
                    print(f"[PIPELINE] ✅ 명령어 처리 성공 (카테고리: {category}, 신뢰도: {confidence:.2f})")
            else:
                # 실패 응답 TTS
                speak_intent_result(intent_result, callback=self._on_command_complete)
                
                if self.debug:
                    confidence = intent_result.get("confidence", 0)
                    error = intent_result.get("error", "Unknown error")
                    print(f"[PIPELINE] ❌ 명령어 처리 실패 (신뢰도: {confidence:.2f}, 오류: {error})")
                
        except Exception as e:
            print(f"[PIPELINE] 명령어 처리 오류: {e}")
            # 오류 응답 TTS
            error_result = {
                "success": False,
                "error": "Command processing error",
                "confidence": 0.0
            }
            speak_intent_result(error_result, callback=self._on_command_complete)

    def _on_command_complete(self, success: bool, text: str):
        """명령어 처리 완료 후 IDLE로 복귀"""
        if self.debug:
            print(f"[PIPELINE] 명령어 TTS 완료 (성공: {success})")
        
        with self.state_lock:
            self._transition_state(PipelineState.IDLE)
            if self.debug:
                print("[PIPELINE] 🏠 IDLE 모드로 복귀 - 다음 Wake word 대기")

    def _on_command_timeout(self):
        """명령어 대기 타임아웃"""
        with self.state_lock:
            if self.state == PipelineState.LISTENING:
                self.stats['timeouts'] += 1
                if self.debug:
                    print(f"[PIPELINE] ⏰ 명령어 대기 타임아웃 ({self.command_timeout}초)")
                
                self._transition_state(PipelineState.COMMAND_PROCESSING)
                speak_timeout_message(callback=self._on_command_complete)

    def _transition_state(self, new_state: PipelineState):
        """상태 전환 (thread-safe)"""
        if self.state != new_state:
            old_state = self.state
            self.state = new_state
            self.stats['state_transitions'] += 1
            
            if self.debug:
                print(f"[PIPELINE] 상태 전환: {old_state.value} → {new_state.value}")

    def _send_to_api(self, original_text: str, intent_result: Dict[str, Any]):
        """HTTP API로 결과 전송 (비동기)"""
        payload = {
            "timestamp": self._get_timestamp(),
            "original_text": original_text,
            "intent": intent_result,
            "source": "voice_pipeline_2stage",
            "pipeline_stats": {
                "wake_word_time": self.last_wake_word_time,
                "command_time": self.last_command_time,
                "processing_duration": time.time() - self.last_wake_word_time
            }
        }
        
        threading.Thread(
            target=self._send_request_with_retry,
            args=(payload,),
            daemon=True
        ).start()

    def _send_request_with_retry(self, payload: Dict[str, Any]):
        """API 요청 재시도 로직"""
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'VoicePipeline-2Stage/1.0'
        }
        
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                if self.debug:
                    print(f"[PIPELINE] API 전송 시도 {attempt}/{MAX_RETRIES}")
                
                resp = requests.post(
                    self.api_endpoint, 
                    json=payload, 
                    headers=headers, 
                    timeout=REQUEST_TIMEOUT
                )
                
                if resp.status_code == 200:
                    self.stats['api_success'] += 1
                    if self.debug:
                        print(f"[PIPELINE] ✅ API 전송 성공")
                        try:
                            response_data = resp.json()
                            print(f"[PIPELINE] API 응답: {response_data}")
                        except:
                            print(f"[PIPELINE] API 응답: {resp.text[:200]}")
                    return
                else:
                    print(f"[PIPELINE] ❌ API 응답 오류: {resp.status_code}")
                    if resp.text:
                        print(f"[PIPELINE] 오류 내용: {resp.text[:200]}")
                        
            except requests.exceptions.Timeout:
                print(f"[PIPELINE] ⏰ API 요청 타임아웃 (시도 {attempt}/{MAX_RETRIES})")
            except requests.exceptions.ConnectionError:
                print(f"[PIPELINE] 🔌 API 연결 실패 (시도 {attempt}/{MAX_RETRIES})")
            except Exception as e:
                print(f"[PIPELINE] 🚨 API 요청 오류 (시도 {attempt}/{MAX_RETRIES}): {e}")

            if attempt < MAX_RETRIES:
                time.sleep(1.0)

        self.stats['api_failed'] += 1
        print(f"[PIPELINE] ❌ API 전송 최종 실패")

    def _get_timestamp(self) -> str:
        """현재 시간 ISO 형식으로 반환"""
        from datetime import datetime
        return datetime.now().isoformat()

    def get_state(self) -> PipelineState:
        """현재 상태 반환"""
        with self.state_lock:
            return self.state

    def get_state_info(self) -> Dict[str, Any]:
        """상태 정보 상세 반환"""
        with self.state_lock:
            return {
                "current_state": self.state.value,
                "is_listening_for_wake_word": self.state == PipelineState.IDLE,
                "is_listening_for_command": self.state == PipelineState.LISTENING,
                "is_processing": self.state in [PipelineState.WAKE_PROCESSING, PipelineState.COMMAND_PROCESSING],
                "command_timer_active": self.command_timer is not None and self.command_timer.is_alive(),
                "tts_ready": self.tts.is_ready()
            }

    def force_reset(self):
        """강제로 IDLE 상태로 리셋"""
        with self.state_lock:
            if self.command_timer:
                self.command_timer.cancel()
                self.command_timer = None
            
            old_state = self.state
            self._transition_state(PipelineState.IDLE)
            
            if self.debug:
                print(f"[PIPELINE] 🔄 강제 리셋: {old_state.value} → IDLE")

    def start(self):
        """파이프라인 시작"""
        print("="*60)
        print("🚀 2단계 대화형 음성 인식 파이프라인 시작")
        print("="*60)
        print(f"[PIPELINE] API 엔드포인트: {self.api_endpoint}")
        print(f"[PIPELINE] 명령어 대기 시간: {self.command_timeout}초")
        print(f"[PIPELINE] Wake word 신뢰도 임계값: {self.wake_word_confidence_threshold}")
        print(f"[PIPELINE] 명령어 신뢰도 임계값: {self.command_confidence_threshold}")
        print()
        print("💡 사용법:")
        print("  1단계: Wake word 말하기 (예: '헤이 숨', '숨')")
        print("  2단계: TTS 응답 후 명령어 말하기 (예: '에어컨 켜줘')")
        print("="*60)

        # TTS 모델 로딩 대기
        print("[PIPELINE] TTS 모델 로딩 중...")
        if not self.tts.wait_ready(timeout=60):
            print("❌ TTS 모델 로딩 실패")
            return
            
        print("✅ TTS 모델 준비 완료")
        print(f"[PIPELINE] 상태: {self.state.value} (Wake word 대기 중)")

        self._start_mqtt()

        # STT 콜백 등록
        stt_whisper.subscribe(self.process_stt_result)

        try:
            # STT 시작
            stt_whisper.main()
        except Exception as e:
            print(f"[PIPELINE] STT 시작 오류: {e}")
            raise

    def stop(self):
        """파이프라인 정지"""
        print("[PIPELINE] 파이프라인 정지 중...")
        
        # STT 콜백 해제
        stt_whisper.unsubscribe(self.process_stt_result)
        
        # 타이머 정리
        with self.state_lock:
            if self.command_timer:
                self.command_timer.cancel()
                self.command_timer = None
        
        # TTS 정지
        self.tts.stop()
        
        print("[PIPELINE] 파이프라인 정지 완료")

    def get_stats(self) -> Dict[str, Any]:
        """통계 반환"""
        stats = self.stats.copy()
        stats.update(self.get_state_info())
        
        # 성공률 계산
        if stats['wake_word_attempts'] > 0:
            stats['wake_word_success_rate'] = (stats['wake_word_success'] / stats['wake_word_attempts']) * 100
        else:
            stats['wake_word_success_rate'] = 0.0
            
        if stats['command_attempts'] > 0:
            stats['command_success_rate'] = (stats['command_success'] / stats['command_attempts']) * 100
        else:
            stats['command_success_rate'] = 0.0
            
        if stats['command_success'] > 0:
            stats['api_success_rate'] = (stats['api_success'] / stats['command_success']) * 100
        else:
            stats['api_success_rate'] = 0.0
        
        return stats

    def print_stats(self):
        """통계 출력"""
        stats = self.get_stats()
        
        print("\n" + "="*50)
        print("📊 2단계 파이프라인 통계")
        print("="*50)
        print(f"현재 상태: {stats['current_state']}")
        print(f"상태 전환 횟수: {stats['state_transitions']}")
        print()
        print("📥 입력 통계:")
        print(f"  총 STT 수신: {stats['total_stt_received']}")
        print()
        print("🎯 1단계 (Wake Word):")
        print(f"  시도: {stats['wake_word_attempts']}")
        print(f"  성공: {stats['wake_word_success']}")
        print(f"  성공률: {stats['wake_word_success_rate']:.1f}%")
        print()
        print("🎯 2단계 (Command):")
        print(f"  시도: {stats['command_attempts']}")
        print(f"  성공: {stats['command_success']}")
        print(f"  성공률: {stats['command_success_rate']:.1f}%")
        print(f"  타임아웃: {stats['timeouts']}")
        print()
        print("🌐 API 전송:")
        print(f"  성공: {stats['api_success']}")
        print(f"  실패: {stats['api_failed']}")
        print(f"  성공률: {stats['api_success_rate']:.1f}%")
        print("="*50)

    def _on_notify_complete(self, success: bool, text: str):
        if self.debug:
            print(f"[PIPELINE] 외부 알림 TTS 완료 (성공: {success})")
        with self.state_lock:
            # 외부 알림이든 뭐든 TTS 끝나면 다시 IDLE
            self._transition_state(PipelineState.IDLE)
            if self.debug:
               print("[PIPELINE] 🏠 IDLE 복귀 (외부 알림 종료)")
    
def test_api_connection():
    """API 연결 테스트"""
    test_payload = {
        "timestamp": "2025-01-01T00:00:00",
        "original_text": "테스트 메시지",
        "intent": {
            "success": True, 
            "category": "test", 
            "command": "connection_test", 
            "confidence": 1.0
        },
        "source": "pipeline_test_2stage"
    }
    
    try:
        r = requests.post(
            API_ENDPOINT, 
            json=test_payload, 
            headers={'Content-Type': 'application/json'}, 
            timeout=5
        )
        print(f"[TEST] API 연결 테스트 결과: {r.status_code}")
        if r.text:
            print(f"[TEST] 응답: {r.text}")
        return r.status_code == 200
    except Exception as e:
        print(f"[TEST] API 연결 테스트 실패: {e}")
        return False

def interactive_test():
    """대화형 테스트 모드"""
    print("\n🧪 대화형 테스트 모드")
    print("명령어:")
    print("  'stats' - 통계 출력")
    print("  'state' - 상태 정보 출력")
    print("  'reset' - 강제 리셋")
    print("  'quit' - 종료")
    print()
    
    pipeline = VoicePipeline(debug=True)
    
    try:
        # 별도 스레드에서 파이프라인 시작
        pipeline_thread = threading.Thread(target=pipeline.start, daemon=True)
        pipeline_thread.start()
        
        time.sleep(2)  # 초기화 대기
        
        while True:
            try:
                cmd = input(">>> ").strip().lower()
                
                if cmd == 'quit':
                    break
                elif cmd == 'stats':
                    pipeline.print_stats()
                elif cmd == 'state':
                    state_info = pipeline.get_state_info()
                    print(f"상태 정보: {json.dumps(state_info, indent=2, ensure_ascii=False)}")
                elif cmd == 'reset':
                    pipeline.force_reset()
                    print("파이프라인 강제 리셋 완료")
                elif cmd == '':
                    continue
                else:
                    print("알 수 없는 명령어")
                    
            except KeyboardInterrupt:
                break
                
    finally:
        pipeline.stop()

if __name__ == "__main__":
    print("🎙️ 2단계 대화형 음성 인식 시스템")
    print()
    
    # API 연결 테스트
    print("[INIT] API 연결 테스트 중...")
    if not test_api_connection():
        print("[WARN] API 서버에 연결할 수 없습니다.")
        print("계속 진행하시겠습니까? (y/N)")
        if input().lower() != 'y':
            import sys
            sys.exit(1)

    # 실행 모드 선택
    print("\n실행 모드를 선택하세요:")
    print("1. 일반 모드 (기본)")
    print("2. 대화형 테스트 모드")
    
    try:
        choice = input("선택 (1-2, 기본값: 1): ").strip()
        
        if choice == '2':
            interactive_test()
        else:
            # 일반 모드
            pipeline = VoicePipeline(
                api_endpoint=API_ENDPOINT, 
                command_timeout=10.0,
                wake_word_confidence_threshold=0.7,
                command_confidence_threshold=0.6,
                debug=True
            )
            
            try:
                pipeline.start()
            except KeyboardInterrupt:
                print("\n[STOP] 파이프라인 종료 중...")
                pipeline.print_stats()
                pipeline.stop()
                import sys
                sys.exit(0)
                
    except KeyboardInterrupt:
        print("\n[STOP] 프로그램 종료")
        import sys
        sys.exit(0)
