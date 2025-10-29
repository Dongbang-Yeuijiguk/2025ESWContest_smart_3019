# tts_kitten.py
import time
import threading
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
import numpy as np
import sounddevice as sd
import queue
import logging
from threading import Event, Timer
from gate import TTS_PLAYING, LAST_TTS_TS

# ──────────────────────────────────────────────────────────────────────────────
# 외부 TTS: kittentts
# pip install kittentts soundfile
# 모델: "KittenML/kitten-tts-nano-0.2"
# 가용 보이스:
#   'expr-voice-2-m','expr-voice-2-f','expr-voice-3-m','expr-voice-3-f',
#   'expr-voice-4-m','expr-voice-4-f','expr-voice-5-m','expr-voice-5-f'
# ──────────────────────────────────────────────────────────────────────────────
from kittentts import KittenTTS as _KittenTTS
import soundfile as sf

SAMPLE_RATE = 24000
DEFAULT_MODEL = "KittenML/kitten-tts-nano-0.2"
DEFAULT_VOICE = "expr-voice-2-f"
AVAILABLE_VOICES: List[str] = [
    "expr-voice-2-m", "expr-voice-2-f",
    "expr-voice-3-m", "expr-voice-3-f",
    "expr-voice-4-m", "expr-voice-4-f",
    "expr-voice-5-m", "expr-voice-5-f",
]


# ── 2단계 대화형 시스템용 응답 메시지 ──
WAKE_WORD_RESPONSES = [
    "Yes, I'm listening.            a",
    "How can I help you.            a", 
    "What can I do for you.            a",
    "I'm ready to help.            a",
    "Go ahead.            a",
    "Yes sir.            a",
    "I'm here.            a",
    "What would you like me to do.            a"
]

TIMEOUT_RESPONSES = [
    "I didn't hear anything. Going back to sleep.            a",
    "No command received. Returning to standby mode.            a",
    "Timeout. I'm going back to sleep mode.            a",
    "I'll wait for your next command.            a",
    "Going back to listening mode.            a"
]

SUCCESS_RESPONSES = {
    "device_control": {
        "ac": [
            "Air conditioner adjusted successfully.            a",
            "AC settings updated.            a",
            "Temperature control activated.            a"
        ],
        "ap": [
            "Air purifier settings updated.            a",
            "Air quality control activated.            a",
            "Purifier mode changed successfully.            a"
        ],
        "light": [
            "Lighting adjusted successfully.            a",
            "Light settings updated.            a",
            "Brightness control activated.            a"
        ],
        "curtain": [
            "Curtain control activated.            a",
            "Window covering adjusted.            a",
            "Curtain position updated.            a"
        ]
    },
    "routine_setting": {
        "set_wake_time": [
            "Wake up alarm set successfully.            a",
            "Morning routine scheduled.            a",
            "Alarm time updated.            a"
        ],
        "snooze_wake": [
            "Alarm snoozed for 10 minutes.            a",
            "Wake up time delayed.            a",
            "Snooze activated.            a"
        ]
    },
    "general": [
        "Command executed successfully.            a",
        "Task completed.            a",
        "Request processed.            a"
    ]
}

FAILURE_RESPONSES = {
    "no_wake_word": [
        "Wake word not detected.            a",
        "Please use the wake word.            a",
        "Command not recognized.            a"
    ],
    "unsupported_device": [
        "Device not supported.            a",
        "Unknown device type.            a",
        "Device not available.            a"
    ],
    "parsing_error": [
        "Could not understand the command.            a",
        "Please try again.            a",
        "Command not clear.            a"
    ],
    "no_parameters": [
        "No valid parameters found.            a",
        "Command incomplete.            a",
        "Missing command details.            a"
    ],
    "general": [
        "Command failed.            a",
        "Unable to process request.            a",
        "Something went wrong.            a"
    ]
}


class KittenTTS:
    """
    kittentts 기반 영어 음성 출력 시스템 (2단계 대화형 지원)
    - 비동기 큐 처리
    - WAV 캐싱
    - sounddevice 재생
    - Wake word 응답 지원
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        voice: str = DEFAULT_VOICE,
        cache_dir: Optional[str] = None,
        max_queue_size: int = 10,
    ):
        if voice not in AVAILABLE_VOICES:
            raise ValueError(f"voice '{voice}' not in AVAILABLE_VOICES: {AVAILABLE_VOICES}")

        self.model_name = model_name
        self.voice = voice

        self.cache_dir = Path(cache_dir) if cache_dir else Path.cwd() / "tts_cache"
        self.cache_dir.mkdir(exist_ok=True)

        # kittentts 모델 핸들
        self.tts_model: Optional[_KittenTTS] = None
        self.model_loaded = False

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

        # 모델 로드 (백그라운드)
        self._load_model_async()

    # ──────────────────────────────────────────────────────────────────────
    # 초기화 & 워커
    # ──────────────────────────────────────────────────────────────────────
    def _load_model_async(self):
        def load_model():
            try:
                self.logger.info(f"Loading KittenTTS model: {self.model_name}")
                start = time.time()
                self.tts_model = _KittenTTS(self.model_name)
                self.model_loaded = True
                self.logger.info(f"KittenTTS loaded in {time.time()-start:.2f}s (CPU, no-GPU).")
                self._start_worker()
            except Exception as e:
                self.logger.error(f"Failed to load KittenTTS: {e}")
                self.model_loaded = False

        threading.Thread(target=load_model, daemon=True).start()

    def _start_worker(self):
        if self.worker_thread and self.worker_thread.is_alive():
            return
        self.running = True
        self.worker_thread = threading.Thread(target=self._tts_worker, daemon=True)
        self.worker_thread.start()
        self.logger.info("TTS worker thread started")

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
        return self.cache_dir / f"{hash((text, self.voice))}.wav"

    def _synthesize_and_play(self, text: str) -> bool:
        if not self.model_loaded or not self.tts_model:
            self.logger.warning("TTS model not loaded")
            self.stats["failed_synthesis"] += 1
            return False

        try:
            start = time.time()
            cache_file = self._cache_path_for(text)

            if cache_file.exists():
                self.logger.debug(f"Using cached audio for: {text!r}")
                audio = self._load_wav(cache_file)
            else:
                self.logger.debug(f"Synthesizing: {text!r} (voice={self.voice})")
                # kittentts: numpy array(float32) 반환을 가정
                audio = self.tts_model.generate(text, voice=self.voice)
                self._save_wav(cache_file, audio)

            if audio is not None and audio.size > 0:
                self._play_audio(audio, SAMPLE_RATE)
                self.logger.info(f"TTS completed in {time.time()-start:.2f}s: {text!r}")
                self.stats["successful_synthesis"] += 1
                return True

        except Exception as e:
            self.logger.error(f"TTS synthesis error: {e}")

        self.stats["failed_synthesis"] += 1
        return False

    def _load_wav(self, path: Path) -> np.ndarray:
        try:
            data, sr = sf.read(str(path), dtype="float32")
            if sr != SAMPLE_RATE:
                # 단순 리샘플 회피: kittentts/캐시 모두 24k로 통일하는 설계
                self.logger.warning(f"Unexpected sample rate {sr}, expected {SAMPLE_RATE}. Playing as-is.")
            if data.ndim > 1:
                data = data.mean(axis=1)
            return data
        except Exception as e:
            self.logger.error(f"Cache load error: {e}")
            return np.array([], dtype=np.float32)

    def _save_wav(self, path: Path, audio: np.ndarray):
        try:
            if audio.dtype != np.float32:
                audio = audio.astype(np.float32)
            sf.write(str(path), audio, SAMPLE_RATE)
            try: 
                self.prune_cache()
            except Exception: 
                pass  
        except Exception as e:
            self.logger.warning(f"Cache save error: {e}")

    def _play_audio(self, audio: np.ndarray, sample_rate: int):
        try:
            # ▶ TTS 시작 시각 기록
            import time as _t
            global LAST_TTS_TS
            LAST_TTS_TS = _t.monotonic()

            TTS_PLAYING.set()

            if audio.dtype != np.float32:
                audio = audio.astype(np.float32)
            # 볼륨 정규화
            peak = float(np.max(np.abs(audio))) if audio.size else 0.0
            if peak > 0:
                audio = audio / peak * 0.8

            sd.stop()    
            sd.play(audio, sample_rate, blocking=True)
            sd.wait()

            LAST_TTS_TS = _t.monotonic()
            Timer(0.30, TTS_PLAYING.clear).start()
        except Exception as e:
            self.logger.error(f"Audio playback error: {e}")
            TTS_PLAYING.clear()

    def prune_cache(self, max_files: int = 1000):
        """캐시 정리 (파일 수 제한)"""
        try:
            cache_files = list(self.cache_dir.glob("*.wav"))
            if len(cache_files) > max_files:
                # 오래된 파일부터 삭제
                cache_files.sort(key=lambda p: p.stat().st_mtime)
                for old_file in cache_files[:-max_files]:
                    old_file.unlink()
                self.logger.info(f"Pruned {len(cache_files) - max_files} old cache files")
        except Exception as e:
            self.logger.warning(f"Cache pruning error: {e}")

    # ──────────────────────────────────────────────────────────────────────
    # 2단계 대화형 시스템용 퍼블릭 API
    # ──────────────────────────────────────────────────────────────────────
    def speak_wake_response(self, callback=None):
        """Wake word 감지 시 응답"""
        import random
        response = random.choice(WAKE_WORD_RESPONSES)
        self.stats["wake_responses"] += 1
        return self.speak(response, callback)

    def speak_timeout_response(self, callback=None):
        """명령어 대기 타임아웃 시 응답"""
        import random
        response = random.choice(TIMEOUT_RESPONSES)
        self.stats["timeout_responses"] += 1
        return self.speak(response, callback)

    def speak_success(self, intent_result: Dict[str, Any], callback=None):
        """성공 응답 (기존 유지)"""
        return self.speak(self._generate_success_response(intent_result), callback)

    def speak_failure(self, intent_result: Dict[str, Any], callback=None):
        """실패 응답 (기존 유지)"""
        return self.speak(self._generate_failure_response(intent_result), callback)

    def speak(self, text: str, callback=None):
        """기본 TTS 메서드"""
        if not text or not text.strip():
            return False
        self.stats["total_requests"] += 1
        try:
            self.tts_queue.put_nowait((text.strip(), callback))
            return True
        except queue.Full:
            self.logger.warning(f"TTS queue full, dropping request: {text!r}")
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
    # 응답 문구 생성 (기존 유지)
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
# 전역 인스턴스 & 헬퍼 함수들
# ──────────────────────────────────────────────────────────────────────────────
_tts_instance: Optional[KittenTTS] = None

def get_tts_instance(voice: str = DEFAULT_VOICE) -> KittenTTS:
    global _tts_instance
    if _tts_instance is None:
        _tts_instance = KittenTTS(model_name=DEFAULT_MODEL, voice=voice)
    return _tts_instance

def speak_intent_result(intent_result: Dict[str, Any], callback=None, voice: str = DEFAULT_VOICE):
    """인텐트 결과에 따른 TTS 응답.
    ✅ response_text/tts_text/message/say 중 하나가 있으면 무조건 그걸 읽는다.
    없을 때만 기존 성공/실패 문구로 폴백.
    """
    tts = get_tts_instance(voice=voice)

    # ★ 우선권: 명시 텍스트
    text = (
        intent_result.get("response_text")
        or intent_result.get("tts_text")
        or intent_result.get("message")
        or intent_result.get("say")
    )
    if text and str(text).strip():
        return tts.speak(str(text).strip(), callback)

    # 폴백: 카테고리 기반 기존 문구
    if intent_result.get("success", False):
        return tts.speak_success(intent_result, callback)
    else:
        return tts.speak_failure(intent_result, callback)

# ── 2단계 대화형 시스템용 전역 함수들 ──
def speak_wake_word_response(callback=None, voice: str = DEFAULT_VOICE):
    """Wake word 감지 시 응답 (전역 함수)"""
    tts = get_tts_instance(voice=voice)
    return tts.speak_wake_response(callback)

def speak_timeout_message(callback=None, voice: str = DEFAULT_VOICE):
    """타임아웃 시 응답 (전역 함수)"""
    tts = get_tts_instance(voice=voice)
    return tts.speak_timeout_response(callback)

def speak_text(text: str, callback=None, voice: str = DEFAULT_VOICE):
    """일반 텍스트 TTS (전역 함수)"""
    tts = get_tts_instance(voice=voice)
    return tts.speak(text, callback)

# ──────────────────────────────────────────────────────────────────────────────
# 테스트
# ──────────────────────────────────────────────────────────────────────────────
def test_tts():
    print("=== 2단계 대화형 TTS 테스트 시작 ===")
    tts = get_tts_instance()
    print("TTS 모델 로딩 중...")
    if not tts.wait_ready(timeout=60):
        print("❌ TTS 모델 로딩 실패")
        return
    print("✅ TTS 모델 로딩 완료")

    # Wake word 응답 테스트
    print("\n1. Wake word 응답 테스트")
    tts.speak_wake_response()
    time.sleep(5)

    # 타임아웃 응답 테스트
    print("\n2. 타임아웃 응답 테스트")
    tts.speak_timeout_response()
    time.sleep(5)

    # 기존 인텐트 응답 테스트
    print("\n3. 인텐트 응답 테스트")
    test_intent = {
        "success": True,
        "category": "device_control",
        "device_type": "ac",
        "payload": {"ac_power": "on", "target_ac_temperature": 24},
    }
    speak_intent_result(test_intent)
    time.sleep(5)

    # 통계 출력
    stats = tts.get_stats()
    print("\n=== TTS 통계 ===")
    print(f"총 요청: {stats['total_requests']}")
    print(f"성공: {stats['successful_synthesis']}")
    print(f"실패: {stats['failed_synthesis']}")
    print(f"큐 드롭: {stats['queue_full_drops']}")
    print(f"Wake word 응답: {stats['wake_responses']}")
    print(f"타임아웃 응답: {stats['timeout_responses']}")

if __name__ == "__main__":
    test_tts()
