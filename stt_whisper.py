import os, sys, time, math, queue, threading, tempfile, uuid
import numpy as np
import sounddevice as sd
import soundfile as sf
import webrtcvad
from faster_whisper import WhisperModel
from gate import TTS_PLAYING

# ===== 설정 =====
SAMPLE_RATE   = 16000
CHANNELS      = 1
FRAME_MS      = int(os.getenv("FRAME_MS", "20"))  # WebRTC VAD: 10, 20, 30ms만 지원
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000
RING_TARGET   = 512

MODEL_SIZE    = os.getenv("WHISPER_MODEL", "base")
DEVICE        = os.getenv("WHISPER_DEVICE", "cpu")
COMPUTE       = os.getenv("WHISPER_COMPUTE", "int8")
LANG          = os.getenv("WHISPER_LANG", "ko")

# VAD 파라미터 - 2단계 시스템에 맞게 최적화
VAD_MODE      = int(os.getenv("VAD_MODE", "3"))       # 0~3, 3이 가장 aggressive
MIN_SPEECH_MS = int(os.getenv("MIN_SPEECH_MS", "150"))  # Wake word용으로 단축
MIN_SIL_MS    = int(os.getenv("MIN_SIL_MS", "200"))    # 더 빠른 반응
PRE_SPEECH_MS = int(os.getenv("PRE_SPEECH_MS", "100")) # 전처리 시간 단축

MIN_SPEECH_FR = max(1, MIN_SPEECH_MS // FRAME_MS)
MIN_SIL_FR    = max(1, MIN_SIL_MS // FRAME_MS)
PRE_SPEECH_FR = max(0, PRE_SPEECH_MS // FRAME_MS)

# 속도 최적화 설정
MAX_AUDIO_LENGTH = int(os.getenv("MAX_AUDIO_LENGTH", "6"))  # Wake word용으로 단축
BEAM_SIZE = int(os.getenv("BEAM_SIZE", "1"))               # 빠른 처리
BEST_OF = int(os.getenv("BEST_OF", "1"))                   # 빠른 처리

# 디버그/장치/프리앰프/우회
DEBUG         = os.getenv("VAD_DEBUG", "1") == "1"
DEVICE_INDEX  = int(os.getenv("SD_INPUT_DEV", "-1"))  # -1이면 기본
AMP_DB        = float(os.getenv("AMP_DB", "6"))       # 소프트 프리앰프 (dB)
GAIN          = float(10 ** (AMP_DB / 20.0))
BYPASS_VAD    = os.getenv("BYPASS_VAD", "0") == "1"   # VAD 우회: 0
SEG_MS        = int(os.getenv("SEG_MS", "1000"))      # 짧은 세그먼트
GAP_MS        = int(os.getenv("GAP_MS", "200"))       # 짧은 간격

# 노이즈 게이트 (WebRTC VAD 보완용)
NOISE_GATE_DB = float(os.getenv("NOISE_GATE_DB", "-60"))  # dBFS 기준

# 큐 크기 최적화 - 2단계 시스템용
audio_q   = queue.Queue(maxsize=50)    # 더 작은 버퍼
segment_q = queue.Queue(maxsize=10)    # 더 작은 버퍼
stop_flag = threading.Event()

# 모델 캐싱 - 매번 로드하지 않도록
_model_cache = None
_model_lock = threading.Lock()

# 파이프라인 연결 - 2단계 시스템용
_subscribers = []

# TTS 잔향(누화) 차단 - 더 강화
REFRACTORY_SEC = 0.8  # 조금 더 길게
_last_tts_seen = 0.0

def tts_blocked() -> bool:
    """TTS 중이거나 잔향 창이면 True - 2단계 시스템용 강화"""
    global _last_tts_seen
    if TTS_PLAYING.is_set():
        _last_tts_seen = time.monotonic()
        return True
    return (time.monotonic() - _last_tts_seen) < REFRACTORY_SEC

def subscribe(callback):
    """STT 결과를 받을 콜백 함수 등록"""
    _subscribers.append(callback)

def unsubscribe(callback):
    """콜백 함수 등록 해제"""
    if callback in _subscribers:
        _subscribers.remove(callback)

def clear_subscribers():
    """모든 구독자 제거"""
    _subscribers.clear()

def _notify_subscribers(text: str):
    """등록된 모든 콜백에 텍스트 전달"""
    for callback in _subscribers:
        try:
            callback(text)
        except Exception as e:
            print(f"[WARN] 콜백 오류: {e}")

def get_model():
    """모델 싱글톤 패턴으로 캐싱"""
    global _model_cache
    with _model_lock:
        if _model_cache is None:
            print(f"[LOAD] faster-whisper model={MODEL_SIZE}, device={DEVICE}, compute={COMPUTE}")
            _model_cache = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE)
            
            # 워밍업 - 첫 실행 지연 방지 (더 작은 샘플로)
            print("[WARMUP] 모델 워밍업 중...")
            dummy_audio = np.random.randn(SAMPLE_RATE // 2).astype(np.float32) * 0.01  # 0.5초 샘플
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                tmp_path = tmp.name
                sf.write(tmp_path, dummy_audio, SAMPLE_RATE, subtype="PCM_16")
            
            try:
                parts, _ = _model_cache.transcribe(tmp_path, language=LANG, beam_size=1, best_of=1)
                list(parts)  # 실제 실행
                print("[WARMUP] 완료")
            except:
                pass
            finally:
                try: os.remove(tmp_path)
                except: pass
    
    return _model_cache

# ===== 유틸 =====
def dbfs_from_int16(x: np.ndarray) -> float:
    if x.size == 0: return -120.0
    rms = np.sqrt(np.mean((x.astype(np.float32))**2))
    return 20*math.log10(max(rms/32767.0, 1e-12))

def dbfs_from_float(x: np.ndarray) -> float:
    if x.size == 0: return -120.0
    rms = np.sqrt(np.mean(x.astype(np.float32)**2))
    return 20*math.log10(max(rms, 1e-12))

def load_webrtc_vad():
    """WebRTC VAD 초기화"""
    global FRAME_MS, FRAME_SAMPLES

    # WebRTC VAD는 10ms, 20ms, 30ms 프레임만 지원
    if FRAME_MS not in [10, 20, 30]:
        print(f"[WARN] WebRTC VAD는 10/20/30ms 프레임만 지원. {FRAME_MS}ms → 20ms로 변경")
        FRAME_MS = 20
        FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000
    
    vad = webrtcvad.Vad()
    vad.set_mode(VAD_MODE)  # 0: 가장 관대, 3: 가장 엄격
    print(f"[VAD] WebRTC VAD 초기화 완료 (mode={VAD_MODE}, frame={FRAME_MS}ms)")
    return vad

# ===== 마이크 =====
def mic_stream():
    level_buf = []; cb_count = 0

    # 장치 정보 로그
    try:
        devinfo = sd.query_devices(DEVICE_INDEX if DEVICE_INDEX>=0 else None)
        print(f"[MIC] using device: {devinfo['name']} (index={DEVICE_INDEX})")
    except Exception as e:
        print(f"[MIC] device query failed: {e}")

    def callback(indata, frames, time_info, status):
        nonlocal cb_count

        # 🔒 TTS 중(또는 잔향 창) → 프레임/큐 즉시 드롭 (강화된 차단)
        if tts_blocked():
            # 대기열까지 싹 비워서 밀린 프레임 제거
            try:
                while True:
                    audio_q.get_nowait()
            except queue.Empty:
                pass
            return

        if status: print(f"[AUDIO]{status}", file=sys.stderr)
        data = indata[:,0] if indata.ndim==2 else indata  # float32 -1..1
        
        # 소프트 프리앰프
        if AMP_DB != 0:
            data = np.clip(data * GAIN, -1.0, 1.0)
            
        # 쪼개서 큐에 - 큐 가득 찬 경우 드롭하여 지연 방지
        for i in range(0, len(data), FRAME_SAMPLES):
            frame = data[i:i+FRAME_SAMPLES]
            if len(frame)==FRAME_SAMPLES:
                try: 
                    audio_q.put_nowait(frame.copy())
                except queue.Full: 
                    # 큐가 가득 찬 경우 오래된 데이터 제거
                    try: audio_q.get_nowait()
                    except queue.Empty: pass
                    try: audio_q.put_nowait(frame.copy())
                    except queue.Full: pass
                    
        cb_count += 1
        if DEBUG and cb_count % 20 == 0:
            level_buf.append(data.copy())
            z = np.concatenate(level_buf) if level_buf else data
            db = dbfs_from_float(z)
            bar = "#"*min(50, max(0,int((db+60)/60*50)))
            print(f"{db:6.1f} dB {bar}")
            level_buf.clear()

    with sd.InputStream(device=DEVICE_INDEX if DEVICE_INDEX>=0 else None,
                        channels=CHANNELS, samplerate=SAMPLE_RATE,
                        dtype='float32', callback=callback, blocksize=FRAME_SAMPLES):
        while not stop_flag.is_set():
            sd.sleep(50)

# ===== WebRTC VAD 세그먼터 (2단계 시스템에 최적화) =====
def vad_segmenter(vad):
    if BYPASS_VAD:
        return bypass_segmenter()   # 우회 모드
    
    # 순환 버퍼로 메모리 효율성 향상
    from collections import deque
    pre_buf = deque(maxlen=PRE_SPEECH_FR)
    seg_buf = []
    speech_count, sil_count = 0, 0
    in_speech = False
    
    print("[INFO] 2단계 WebRTC VAD 대기 중… Wake word를 말하세요.")
    
    while not stop_flag.is_set():
        # TTS 차단 강화
        if tts_blocked():
            # 진행 중인 세그먼트/버퍼 전부 리셋
            pre_buf.clear(); seg_buf.clear()
            speech_count = sil_count = 0
            in_speech = False
            # 마이크 누적 프레임도 비워서 지연 제거
            try:
                while True:
                    audio_q.get_nowait()
            except queue.Empty:
                pass
            time.sleep(0.01)
            continue
            
        try: 
            frame = audio_q.get(timeout=0.05)  # 더 빠른 응답
        except queue.Empty: 
            continue

        # 노이즈 게이트 체크 (WebRTC VAD 보완)
        db_frame = dbfs_from_float(frame)
        if db_frame < NOISE_GATE_DB:
            is_speech = False
        else:
            # WebRTC VAD는 int16 PCM 데이터가 필요
            frame_int16 = np.int16(np.clip(frame, -1.0, 1.0) * 32767)
            frame_bytes = frame_int16.tobytes()
            
            try:
                is_speech = vad.is_speech(frame_bytes, SAMPLE_RATE)
            except Exception as e:
                if DEBUG:
                    print(f"[VAD] WebRTC VAD 오류: {e}")
                is_speech = False

        # 문두 버퍼 관리 - deque 사용으로 자동 크기 관리
        pre_buf.append(frame)

        # VAD 상태머신 - 2단계 시스템에 맞게 조정
        if is_speech:
            sil_count = 0
            speech_count += 1
            
            # 음성 시작 감지 (더 빠른 반응)
            if not in_speech and speech_count >= 1:
                seg_buf.extend(pre_buf)
                in_speech = True
                if DEBUG:
                    print(f"[VAD] >>> START (level={db_frame:.1f}dBFS)")
            
            seg_buf.append(frame)
            
        else:  # 침묵
            speech_count = 0
            
            if in_speech:
                sil_count += 1
                seg_buf.append(frame)
                
                # 충분한 침묵으로 음성 종료 (더 빠른 반응)
                if sil_count >= MIN_SIL_FR:
                    seg = np.concatenate(seg_buf).astype(np.float32)
                    
                    # 길이 제한으로 처리 속도 향상 (2단계 시스템용)
                    max_samples = MAX_AUDIO_LENGTH * SAMPLE_RATE
                    if seg.size > max_samples:
                        seg = seg[-max_samples:]  # 뒷부분만 사용
                    
                    # 최소 음성 길이 체크 (더 관대하게)
                    if seg.size > 0 and len(seg_buf) >= MIN_SPEECH_FR:
                        seg_i16 = np.int16(np.clip(seg, -1.0, 1.0) * 32767)
                        
                        if DEBUG:
                            dur = int(seg.size * 1000 / SAMPLE_RATE)
                            lvl = dbfs_from_int16(seg_i16)
                            print(f"[VAD] <<< END dur={dur}ms level={lvl:.1f}dBFS")
                        
                        try: 
                            segment_q.put_nowait(seg_i16)
                        except queue.Full: 
                            # 큐가 가득 찬 경우 오래된 세그먼트 제거
                            try: segment_q.get_nowait()
                            except queue.Empty: pass
                            try: segment_q.put_nowait(seg_i16)
                            except queue.Full: pass
                    
                    # 상태 초기화
                    seg_buf.clear()
                    in_speech = False
                    sil_count = 0

# ===== 우회 세그먼터 (2단계 시스템용) =====
def bypass_segmenter():
    print("[INFO] BYPASS_VAD=1 → 고정 구간으로 바로 STT 보냄 (2단계 모드)")
    buf = []
    seg_len = max(1, SEG_MS // FRAME_MS)      # 프레임 단위
    gap_len = max(0, GAP_MS // FRAME_MS)
    
    while not stop_flag.is_set():
        try: frame = audio_q.get(timeout=0.05)  # 더 빠른 응답
        except queue.Empty: continue
        
        buf.append(frame)
        if len(buf) >= seg_len:
            seg = np.concatenate(buf).astype(np.float32)
            buf.clear()
            
            if gap_len:  # 약간의 간격
                for _ in range(gap_len):
                    try: audio_q.get_nowait()
                    except queue.Empty: break
                    
            seg_i16 = np.int16(np.clip(seg, -1.0, 1.0) * 32767)
            try: segment_q.put_nowait(seg_i16)
            except queue.Full: 
                # 큐가 가득 찬 경우 오래된 세그먼트 제거
                try: segment_q.get_nowait()
                except queue.Empty: pass
                try: segment_q.put_nowait(seg_i16)
                except queue.Full: pass

# ===== 최적화된 STT 워커 (2단계 시스템용) =====
def stt_worker():
    model = get_model()  # 캐시된 모델 사용
    
    while not stop_flag.is_set():
        try: seg = segment_q.get(timeout=0.05)  # 더 빠른 응답
        except queue.Empty: continue
        
        # 🔒 TTS 중/잔향 창 → 세그먼트 폐기 (강화된 차단)
        if tts_blocked():
            segment_q.task_done() if hasattr(segment_q, "task_done") else None
            continue

        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp_path = tmp.name
            sf.write(tmp_path, seg, SAMPLE_RATE, subtype="PCM_16")
        
        try:
            t0=time.time()
            
            # 최적화된 파라미터로 추론 (2단계 시스템용)
            parts, info = model.transcribe(
                tmp_path, 
                language=LANG, 
                vad_filter=False,  # VAD는 이미 적용됨
                beam_size=BEAM_SIZE,
                best_of=BEST_OF,
                temperature=0.0,   # 결정론적 디코딩으로 속도 향상
                condition_on_previous_text=False  # 이전 텍스트 의존성 제거
            )
            
            text="".join([p.text for p in parts]).strip()
            
            # 기존 출력 (2단계 시스템 표시)
            print("\n----- [2-STAGE STT RESULT] -----")
            print(text if text else "(빈 결과)")
            print(f"[latency] {(time.time()-t0)*1000:.0f} ms | [level] {dbfs_from_int16(seg):.1f} dBFS")
            print("--------------------------------")
            
            # 구독자들에게 알림 (파이프라인으로 전달)
            if text:
                _notify_subscribers(text)
                
        except Exception as e:
            print(f"[STT] 오류: {e}")
        finally:
            try: os.remove(tmp_path)
            except: pass

def transcribe_file(path: str):
    """오디오 파일 하나 받아서 Whisper로 STT (파일 모드)"""
    if not os.path.exists(path):
        print(f"[ERR] 파일 없음: {path}")
        return ""

    print(f"[FILE] 입력 파일: {path}")
    model = get_model()  # 캐시된 모델 사용

    # wav/mp3 같은 포맷을 전부 soundfile로 로드
    audio, sr = sf.read(path, dtype="float32")
    if audio.ndim > 1:
        audio = audio[:,0]  # 모노로
    if sr != SAMPLE_RATE:
        try:
            import librosa
            audio = librosa.resample(audio, orig_sr=sr, target_sr=SAMPLE_RATE)
            sr = SAMPLE_RATE
        except ImportError:
            print("[WARN] librosa 없음. 리샘플링 생략.")

    # 임시 파일로 저장 후 STT (faster-whisper는 파일 경로에서 더 안정적)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp_path = tmp.name
        sf.write(tmp_path, audio, SAMPLE_RATE, subtype="PCM_16")

    try:
        segs, info = model.transcribe(
            tmp_path, 
            language=LANG, 
            vad_filter=True,
            beam_size=BEAM_SIZE,
            best_of=BEST_OF,
            temperature=0.0
        )
        text = "".join([s.text for s in segs]).strip()
        print("\n===== FILE STT RESULT =====")
        print(text if text else "(빈 결과)")
        print("============================")
        return text
    finally:
        try: os.remove(tmp_path)
        except: pass

# ===== 상태 관리 함수들 (2단계 시스템용) =====
def get_stats():
    """STT 시스템 통계 반환"""
    return {
        "audio_queue_size": audio_q.qsize(),
        "segment_queue_size": segment_q.qsize(),
        "subscribers_count": len(_subscribers),
        "tts_blocked": tts_blocked(),
        "model_loaded": _model_cache is not None
    }

def clear_queues():
    """모든 큐 비우기"""
    try:
        while True:
            audio_q.get_nowait()
    except queue.Empty:
        pass
    
    try:
        while True:
            segment_q.get_nowait()
    except queue.Empty:
        pass

# ===== 메인 =====
def main():
    if len(sys.argv) > 1:
        # 인자로 파일 들어오면 파일 모드
        path = sys.argv[1]
        transcribe_file(path)
    else:
        # 아니면 실시간 모드 (2단계 시스템)
        try:
            vad = None if BYPASS_VAD else load_webrtc_vad()
            t_mic=threading.Thread(target=mic_stream,daemon=True)
            t_vad=threading.Thread(target=vad_segmenter,args=(vad,),daemon=True)
            t_stt=threading.Thread(target=stt_worker,daemon=True)
            t_mic.start(); t_vad.start(); t_stt.start()
            print("[START] 2단계 대화형 WebRTC VAD + STT 시작. Ctrl+C 종료.")
            print("[INFO] Wake word → 명령어 순서로 동작합니다.")
            while True: time.sleep(0.5)
        except KeyboardInterrupt:
            print("\n[STOP] 종료 중…"); stop_flag.set(); time.sleep(0.5)

if __name__=="__main__":
    main()
