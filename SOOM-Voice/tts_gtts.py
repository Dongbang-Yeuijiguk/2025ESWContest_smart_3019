# tts_gtts.py  — KittenTTS 인터페이스 동일, gTTS + playsound 사용(블로킹)
import time
import threading
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
import queue
import logging
from threading import Timer
from gate import TTS_PLAYING, LAST_TTS_TS  # 외부에서 제공됨

# ──────────────────────────────────────────────────────────────────────────────
# 외부 TTS: gTTS + playsound
# pip install gTTS playsound==1.2.2
# gTTS는 MP3만 저장 → 캐시 MP3 재생(playsound, blocking)
# ──────────────────────────────────────────────────────────────────────────────
from gtts import gTTS
from playsound import playsound

# gTTS 기본 설정
DEFAULT_LANG = "en"     # 필요하면 "en"으로 바꿔라
DEFAULT_TLD  = "com"    # 'co.kr', 'co.uk', 'com.au', 'co.in' 등 악센트/지역
DEFAULT_SLOW = False

# KittenTTS 호환을 위해 더미 보이스 목록 유지(의미 없음)
AVAILABLE_VOICES: List[str] = [
    "expr-voice-2-m", "expr-voice-2-f",
    "expr-voice-3-m", "expr-voice-3-f",
    "expr-voice-4-m", "expr-voice-4-f",
    "expr-voice-5-m", "expr-voice-5-f",
]
DEFAULT_VOICE = "expr-voice-2-f"

# ── 2단계 대화형 시스템용 응답 메시지(원본 유지, 필요시 네가 정리해라) ──
WAKE_WORD_RESPONSES = [
    "Yes, I'm listening.",
    "How can I help you.",
    "What can I do for you.",
    "I'm ready to help.",
    "Go ahead.",
    "Yes sir.",
    "I'm here.",
    "What would you like me to do."
]

TIMEOUT_RESPONSES = [
    "I didn't hear anything. Going back to sleep.",
    "No command received. Returning to standby mode.",
    "Timeout. I'm going back to sleep mode.",
    "I'll wait for your next command.",
    "Going back to listening mode."
]

SUCCESS_RESPONSES = {
    "device_control": {
        "ac": [
            "Air conditioner adjusted successfully.",
            "AC settings updated.",
            "Temperature control activated."
        ],
        "ap": [
            "Air purifier settings updated.",
            "Air quality control activated.",
            "Purifier mode changed successfully."
        ],
        "light": [
            "Lighting adjusted successfully.",
            "Light settings updated.",
            "Brightness control activated."
        ],
        "curtain": [
            "Curtain control activated.",
            "Window covering adjusted.",
            "Curtain position updated."
        ]
    },
    "routine_setting": {
        "set_wake_time": [
            "Wake up alarm set successfully.",
            "Morning routine scheduled.",
            "Alarm time updated."
        ],
        "snooze_wake": [
            "Alarm snoozed for 10 minutes.",
            "Wake up time delayed.",
            "Snooze activated."
        ]
    },
    "general": [
        "Command executed successfully.",
        "Task completed.",
        "Request processed."
    ]
}

FAILURE_RESPONSES = {
    "no_wake_word": [
        "Wake word not detected.",
        "Please use the wake word.",
        "Command not recognized."
    ],
    "unsupported_device": [
        "Device not supported.",
        "Unknown device type.",
        "Device not available."
    ],
    "parsing_error": [
        "Could not understand the command.",
        "Please try again.",
        "Command not clear."
    ],
    "no_parameters": [
        "No valid parameters found.",
        "Command incomplete.",
        "Missing command details."
    ],
    "general": [
        "Command failed.",
        "Unable to process request.",
        "Something went wrong."
    ]
}


class KittenTTS:
    """
    gTTS 기반 영어/한국어 음성 출력 (2단계 대화형 지원)
    - 비동기 큐 처리
    - MP3 캐싱
    - playsound 재생(블로킹)
    - Wake word/Timeout 응답 지원
    - 원본 KittenTTS 인터페이스와 동일하게 동작
    """

    def __init__(
        self,
        model_name: str = "gTTS",         # 호환용 더미
        voice: str = DEFAULT_VOICE,       # 호환용 더미
        cache_dir: Optional[str] = None,
        max_queue_size: int = 10,
        lang: str = DEFAULT_LANG,
        tld: str = DEFAULT_TLD,
        slow: bool = DEFAULT_SLOW,
    ):
        if voice not in AVAILABLE_VOICES:
            raise ValueError(f"voice '{voice}' not in AVAILABLE_VOICES: {AVAILABLE_VOICES}")

        self.voice = voice  # 의미 없음(호환성 유지)
        self.lang = lang
        self.tld = tld
        self.slow = slow

        self.cache_dir = Path(cache_dir) if cache_dir else Path.cwd() / "tts_cache"
        self.cache_dir.mkdir(exist_ok=True)

        # gTTS는 사전 로드 불필요 → 플래그만 true
        self.model_loaded = True

        # 비동기 처리
        self.tts_queue: "queue.Queue[Tuple[Optional[str], Optional[Any]]]" = queue.Queue(maxsize=max_queue_size)
        self.worker_thread: Optional[threading.Thread] = None
        self.running = False

        # 통계
        self.stats = {
            "total_requests": 0,
            "successful_synthesis": 0,
            "failed_synthesis": 0,
            "queue_full_drops": 0,
            "wake_responses": 0,
            "timeout_responses": 0,
        }

        # 로깅
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

        # 워커 시작
        self._start_worker()

    # ──────────────────────────────────────────────────────────────────────
    # 워커
    # ──────────────────────────────────────────────────────────────────────
    def _start_worker(self):
        if self.worker_thread and self.worker_thread.is_alive():
            return
        self.running = True
        self.worker_thread = threading.Thread(target=self._tts_worker, daemon=True)
        self.worker_thread.start()
        self.logger.info("TTS worker thread started (gTTS + playsound)")

    def _tts_worker(self):
        while self.running:
            try:
                text, callback = self.tts_queue.get(timeout=1.0)
                if text is None:  # 종료 신호
                    break
                success = self._synthesize_and_play(text)
                if callback:
                    try:
                        callback(success, text)
                    except Exception as e:
                        self.logger.error(f"Callback error: {e}")
                self.tts_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"TTS worker error: {e}")

    # ──────────────────────────────────────────────────────────────────────
    # 합성·재생·캐시
    # ──────────────────────────────────────────────────────────────────────
    def _cache_path_for(self, text: str) -> Path:
        # 텍스트+언어+지역+tld+속도까지 포함해서 해시
        key = (text, self.lang, self.tld, self.slow, self.voice)
        return self.cache_dir / f"{hash(key)}.mp3"

    def _synthesize_and_play(self, text: str) -> bool:
        if not self.model_loaded:
            self.logger.warning("TTS not ready")
            self.stats["failed_synthesis"] += 1
            return False

        try:
            start = time.time()
            cache_file = self._cache_path_for(text)
            if not cache_file.exists():
                # 합성
                self.logger.debug(f"Synthesizing(gTTS): {text!r} (lang={self.lang}, tld={self.tld}, slow={self.slow})")
                tts = gTTS(text=text, lang=self.lang, tld=self.tld, slow=self.slow)
                # 경로 문제(윈도우 259) 줄이려고 절대경로로 저장
                tts.save(str(cache_file.resolve()))
                try:
                    self.prune_cache()
                except Exception:
                    pass

            # 재생 (블로킹)
            self._play_mp3(cache_file.resolve())
            self.logger.info(f"TTS completed in {time.time()-start:.2f}s: {text!r}")
            self.stats["successful_synthesis"] += 1
            return True

        except Exception as e:
            self.logger.error(f"TTS synthesis/playback error: {e}")

        self.stats["failed_synthesis"] += 1
        return False

    def _play_mp3(self, path: Path):
        try:
            import time as _t
            global LAST_TTS_TS

            # 상태 비트 올림
            LAST_TTS_TS = _t.monotonic()
            TTS_PLAYING.set()

            # 윈도우 playsound 259 회피 팁:
            # - 절대경로 사용
            # - 파일 닫힌 상태 보장(gTTS.save는 닫힌다)
            # - 경로에 따옴표, 이상한 제어문자 없도록
            mp3_path = str(path)

            # 혹시 모를 선행 재생 정지 같은 건 playsound에는 없음. 바로 블로킹 재생.
            playsound(mp3_path)  # blocking

            LAST_TTS_TS = _t.monotonic()
            Timer(0.30, TTS_PLAYING.clear).start()

        except Exception as e:
            self.logger.error(f"Audio playback error (playsound): {e}")
            TTS_PLAYING.clear()

    def prune_cache(self, max_files: int = 1000):
        """캐시 정리 (파일 수 제한)"""
        try:
            cache_files = list(self.cache_dir.glob("*.mp3"))
            if len(cache_files) > max_files:
                cache_files.sort(key=lambda p: p.stat().st_mtime)
                for old_file in cache_files[:-max_files]:
                    try:
                        old_file.unlink()
                    except Exception:
                        pass
                self.logger.info(f"Pruned {len(cache_files) - max_files} old cache files")
        except Exception as e:
            self.logger.warning(f"Cache pruning error: {e}")

    # ──────────────────────────────────────────────────────────────────────
    # 2단계 대화형 시스템용 퍼블릭 API
    # ──────────────────────────────────────────────────────────────────────
    def speak_wake_response(self, callback=None):
        import random
        response = random.choice(WAKE_WORD_RESPONSES)
        self.stats["wake_responses"] += 1
        return self.speak(response, callback)

    def speak_timeout_response(self, callback=None):
        import random
        response = random.choice(TIMEOUT_RESPONSES)
        self.stats["timeout_responses"] += 1
        return self.speak(response, callback)

    def speak_success(self, intent_result: Dict[str, Any], callback=None):
        return self.speak(self._generate_success_response(intent_result), callback)

    def speak_failure(self, intent_result: Dict[str, Any], callback=None):
        return self.speak(self._generate_failure_response(intent_result), callback)

    def speak(self, text: str, callback=None):
        if not text or not str(text).strip():
            return False
        clean = str(text).strip()
        self.stats["total_requests"] += 1
        try:
            self.tts_queue.put_nowait((clean, callback))
            return True
        except queue.Full:
            self.logger.warning(f"TTS queue full, dropping request: {clean!r}")
            self.stats["queue_full_drops"] += 1
            return False

    def is_ready(self) -> bool:
        return self.model_loaded and self.running

    def wait_ready(self, timeout: float = 30.0) -> bool:
        start = time.time()
        while not self.is_ready() and (time.time() - start) < timeout:
            time.sleep(0.1)
        return self.is_ready()

    def get_stats(self) -> Dict[str, int]:
        return self.stats.copy()

    def stop(self):
        self.logger.info("Stopping TTS system...")
        self.running = False
        try:
            self.tts_queue.put_nowait((None, None))
        except queue.Full:
            pass
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=5.0)
        self.logger.info("TTS system stopped")

    # ──────────────────────────────────────────────────────────────────────
    # 응답 문구 생성 (원본 유지)
    # ──────────────────────────────────────────────────────────────────────
    def _generate_success_response(self, intent_result: Dict[str, Any]) -> str:
        import random
        category = intent_result.get("category", "general")
        if category == "device_control":
            device_type = intent_result.get("device_type", "general")
            responses = SUCCESS_RESPONSES["device_control"].get(device_type, SUCCESS_RESPONSES["general"])
        elif category == "routine_setting":
            command = intent_result.get("command", "general")
            responses = SUCCESS_RESPONSES["routine_setting"].get(command, SUCCESS_RESPONSES["general"])
        else:
            responses = SUCCESS_RESPONSES["general"]
        return random.choice(responses)

    def _generate_failure_response(self, intent_result: Dict[str, Any]) -> str:
        import random
        error = (intent_result.get("error") or "").lower()
        if "wake word" in error or "시동어" in error:
            responses = FAILURE_RESPONSES["no_wake_word"]
        elif "device" in error or "디바이스" in error:
            responses = FAILURE_RESPONSES["unsupported_device"]
        elif "parameter" in error or "파라미터" in error:
            responses = FAILURE_RESPONSES["no_parameters"]
        else:
            responses = FAILURE_RESPONSES["general"]
        return random.choice(responses)


# ──────────────────────────────────────────────────────────────────────────────
# 전역 인스턴스 & 헬퍼 함수들 (원본과 동일 시그니처)
# ──────────────────────────────────────────────────────────────────────────────
_tts_instance: Optional[KittenTTS] = None

def get_tts_instance(voice: str = DEFAULT_VOICE, **kwargs) -> KittenTTS:
    global _tts_instance
    if _tts_instance is None:
        _tts_instance = KittenTTS(voice=voice, **kwargs)
    return _tts_instance

def speak_intent_result(intent_result: Dict[str, Any], callback=None, voice: str = DEFAULT_VOICE, **kwargs):
    """인텐트 결과에 따른 TTS 응답.
    ✅ response_text/tts_text/message/say 중 하나가 있으면 무조건 그걸 읽는다.
    없을 때만 기존 성공/실패 문구로 폴백.
    """
    tts = get_tts_instance(voice=voice, **kwargs)
    text = (
        intent_result.get("response_text")
        or intent_result.get("tts_text")
        or intent_result.get("message")
        or intent_result.get("say")
    )
    if text and str(text).strip():
        return tts.speak(str(text).strip(), callback)

    if intent_result.get("success", False):
        return tts.speak_success(intent_result, callback)
    else:
        return tts.speak_failure(intent_result, callback)

def speak_wake_word_response(callback=None, voice: str = DEFAULT_VOICE, **kwargs):
    tts = get_tts_instance(voice=voice, **kwargs)
    return tts.speak_wake_response(callback)

def speak_timeout_message(callback=None, voice: str = DEFAULT_VOICE, **kwargs):
    tts = get_tts_instance(voice=voice, **kwargs)
    return tts.speak_timeout_response(callback)

def speak_text(text: str, callback=None, voice: str = DEFAULT_VOICE, **kwargs):
    tts = get_tts_instance(voice=voice, **kwargs)
    return tts.speak(text, callback)

# ──────────────────────────────────────────────────────────────────────────────
# 테스트
# ──────────────────────────────────────────────────────────────────────────────
def test_tts():
    print("=== 2단계 대화형 TTS(gTTS+playsound) 테스트 시작 ===")
    tts = get_tts_instance(lang=DEFAULT_LANG, tld=DEFAULT_TLD, slow=DEFAULT_SLOW)
    print("TTS 준비 확인 중...")
    if not tts.wait_ready(timeout=10):
        print("❌ TTS 준비 실패")
        return
    print("✅ TTS 준비 완료")

    print("\n1. Wake word 응답 테스트")
    tts.speak_wake_response()
    time.sleep(3)

    print("\n2. 타임아웃 응답 테스트")
    tts.speak_timeout_response()
    time.sleep(3)

    print("\n3. 인텐트 응답 테스트")
    test_intent = {
        "success": True,
        "category": "device_control",
        "device_type": "ac",
        "payload": {"ac_power": "on", "target_ac_temperature": 24},
    }
    speak_intent_result(test_intent)
    time.sleep(3)

    stats = tts.get_stats()
    print("\n=== TTS 통계 ===")
    for k, v in stats.items():
        print(f"{k}: {v}")

if __name__ == "__main__":
    test_tts()
