import re
from typing import Dict, Any, Tuple, Optional, Set
from datetime import datetime, timedelta
from functools import lru_cache
import time

# --- 성능 최적화를 위한 정규식 사전 컴파일 ---
class CompiledPatterns:
    """정규식 패턴들을 미리 컴파일해서 성능 향상"""
    
    def __init__(self):
        # 시간 파싱용 패턴들
        self.time_hhmm = re.compile(r"\b(\d{1,2}):(\d{2})\b")
        self.time_half = re.compile(r"(\d{1,2})\s*시\s*반")
        self.time_hour_min = re.compile(r"(\d{1,2})\s*시(?:\s*(\d{1,2})\s*분)?")
        
        # 온도/습도 파싱
        self.temperature = re.compile(r"(?:온도|temp)?\s*([1-4]?\d(?:\.\d)?)\s*도")
        self.temperature_simple = re.compile(r"\b([1-3]?\d)\b")
        self.humidity = re.compile(r"(?:습도)?\s*([3-8]\d)\s*%")
        
        # 기타 파싱
        self.pm_level = re.compile(r"(?:미세먼지|pm)?\s*([1-9]\d?)\s*(?:이하|까지|미만)?")
        self.brightness_percent = re.compile(r"(\d{1,3})\s*%")
        self.brightness_stage = re.compile(r"([0-4])\s*단계")
        self.kelvin = re.compile(r"(\d{4})\s*k")
        self.date_pattern = re.compile(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일")
        
        # 한국어 숫자 변환용
        self.korean_numbers = re.compile(r"(한|두|세|네|다섯|여섯|일곱|여덟|아홉|열|열한|열두)시")

# 전역 패턴 인스턴스
PATTERNS = CompiledPatterns()

# --- 2단계 시스템용 시동어 시스템 ---
# Wake word (1단계에서만 사용)
WAKE_WORDS = {
    # 기본 시동어들 
    "숨", "soom", "헤이 숨", "hey soom", "sum", "수움", "헤이", "에이", "에이 송", "에이, 송", "에이솜", "해이 송", "수음",
    "헐 이쑤", "헐이 숨", "희희성", "에이, 숨!", "선", "희희 송", "에이, 숨.", "이", "이.", "이 .", "hey", "해이", "혜이"
    
    # 단순 호출어 (2단계 시스템에서는 더 간단하게)
    "음성인식", "명령", "실행", "시작"
}

# 디바이스별 시동어는 2단계에서는 제거 (명령어에서만 사용)
DEVICE_WAKE_WORDS = {
    "에어컨","에컨","에시에이씨","aircon","에어 콘","냉난방기",
    "공기청정기","공청기","청정기","air purifier","공기 청정기",
    "조명","불","전등","램프","light",
    "커튼","블라인드","blind","커덴","커턴",
    "알람", "기상", "깨워줘"
}

# 빠른 검색을 위한 Set 변환
WAKE_WORDS_SET: Set[str] = set(WAKE_WORDS)
DEVICE_WAKE_WORDS_SET: Set[str] = set(DEVICE_WAKE_WORDS)

# --- 캐시된 매핑 테이블 ---
DEVICE_ALIASES = {
    "air_conditioner": {"에어컨","에컨","에시에이씨","aircon","에어 콘","냉난방기"},
    "air_purifier": {"공기청정기","공청기","청정기","air purifier","공기 청정기"},
    "smart_light": {"조명","불","전등","램프","light"},
    "smart_curtain": {"커튼","블라인드","blind","커덴","커턴","컷은","같은"},
}

POWER_ON = {"켜","켜져","켜줘","켜라","on","열어","올려"}
POWER_OFF = {"꺼","꺼져","꺼줘","꺼라","off","닫아","내려"}

AC_MODES = {
    "냉방":"cool","시원":"cool","쿨":"cool","cool":"cool",
    "난방":"heat","따뜻":"heat","히트":"heat","heat":"heat",
    "제습":"dry","드라이":"dry","dry":"dry",
    "자동":"auto","오토":"auto","auto":"auto",
}

AP_MODES = {
    "자동":"auto","오토":"auto","auto":"auto",
    "청정":"clean","클린":"clean","clean":"clean",
    "순환":"circulator","써큘레이터":"circulator","circulator":"circulator",
    "듀얼":"dual_clean","듀얼클린":"dual_clean","dual_clean":"dual_clean"
}

CCT_MAP = {
    "전구색":3000,"따뜻":3000,"노란":3000,"warm":3000,
    "주백색":4000,"뉴트럴":4000,"neutral":4000,"중간":4000,
    "주광색":6500,"하얀":6500,"차갑":6500,"쿨":6500,"cool":6500
}

BRIGHTNESS_LEVELS = {
    "꺼":0, "끄기":0, "최저":0, "0":0,
    "어둡게":25, "약간 어둡게":25, "1":25, "1단계":25,
    "보통":50, "중간":50, "2":50, "2단계":50,
    "밝게":75, "약간 밝게":75, "3":75, "3단계":75,
    "최대":100, "최고":100, "아주 밝게":100, "4":100, "4단계":100
}

# 한국어 숫자 매핑 (캐시용)
KOREAN_NUM_MAP = {
    "한시":"1시","두시":"2시","세시":"3시","네시":"4시","다섯시":"5시","여섯시":"6시",
    "일곱시":"7시","여덟시":"8시","아홉시":"9시","열시":"10시","열한시":"11시","열두시":"12시"
}

# --- 최적화된 유틸 함수들 ---
@lru_cache(maxsize=1000)
def _normalize_cached(text: str) -> str:
    """캐시된 텍스트 정규화"""
    return re.sub(r"\s+", " ", text.strip().lower())

def _today_kst():
    """KST 기준 오늘 날짜 (캐시 없음 - 날짜는 변경됨)"""
    return (datetime.utcnow() + timedelta(hours=9)).date()

# --- 2단계 시스템용 Wake word 체크 ---
def check_wake_word(text: str) -> Tuple[bool, float]:
    """
    Wake word만 체크 (2단계 시스템 1단계용)
    Returns: (시동어_발견여부, 신뢰도)
    """
    normalized = _normalize_cached(text)
    
    # 기본 Wake word 직접 매칭 (가장 빠름)
    for wake_word in WAKE_WORDS_SET:
        if wake_word in normalized:
            return True, 0.95
    
    # 부분 매칭 (조금 더 관대한 매칭)
    for wake_word in WAKE_WORDS_SET:
        if len(wake_word) >= 2 and wake_word in normalized:
            return True, 0.8
    
    # 디바이스 시동어도 Wake word로 인정 (하위 호환)
    for device_word in DEVICE_WAKE_WORDS_SET:
        if device_word in normalized:
            return True, 0.7
    
    return False, 0.0

def check_wake_word_strict(text: str) -> Tuple[bool, float]:
    """
    엄격한 Wake word 체크 (기본 시동어만)
    2단계 시스템에서 더 정확한 Wake word 감지
    """
    normalized = _normalize_cached(text)
    
    # 기본 Wake word만 체크
    for wake_word in WAKE_WORDS_SET:
        if wake_word in normalized:
            return True, 0.95
    
    return False, 0.0

def is_pure_wake_word(text: str) -> bool:
    """
    순수한 Wake word인지 확인 (명령어가 섞이지 않음)
    2단계 시스템 1단계에서 사용
    """
    normalized = _normalize_cached(text)
    words = normalized.split()
    
    # Wake word만 있고 다른 명령어가 없는지 확인
    has_wake_word = any(word in WAKE_WORDS_SET for word in words)
    has_device_command = any(word in DEVICE_ALIASES.get(device, set()) 
                           for device in DEVICE_ALIASES for word in words)
    has_power_command = any(word in (POWER_ON | POWER_OFF) for word in words)
    
    return has_wake_word and not (has_device_command or has_power_command)

# --- 최적화된 파싱 함수들 ---
@lru_cache(maxsize=500)
def _find_device_cached(text: str) -> Tuple[Optional[str], float]:
    """캐시된 디바이스 찾기"""
    for device_type, keywords in DEVICE_ALIASES.items():
        for keyword in keywords:
            if keyword in text:
                return device_type, 0.9
    
    if any(w in text for w in ["커튼","블라인드"]):
        return "curtain", 0.6
    
    return None, 0.0

def _parse_power_fast(text: str, device: str) -> Tuple[Optional[str], float]:
    """최적화된 전원 파싱"""
    # Set intersection 사용으로 빠른 검색
    text_words = set(text.split())
    
    if POWER_ON & text_words:
        return "on", 0.9
    if POWER_OFF & text_words:
        return "off", 0.9
    
    # 커튼 특별 처리
    if device == "smart_curtain":
        if "열" in text: return "on", 0.7
        if "닫" in text: return "off", 0.7
    
    return None, 0.0

def _parse_temperature_fast(text: str) -> Tuple[Optional[float], float]:
    """최적화된 온도 파싱"""
    # 사전 컴파일된 패턴 사용
    m = PATTERNS.temperature.search(text)
    if m:
        v = float(m.group(1))
        if 10.0 <= v <= 35.0: 
            return v, 0.85
    
    m = PATTERNS.temperature_simple.search(text)
    if m:
        v = float(m.group(1))
        if 16 <= v <= 30:
            return v, 0.7
    
    return None, 0.0

def _parse_time_ko_fast(text: str) -> Tuple[Optional[str], float]:
    """최적화된 시간 파싱"""
    # 한국어 숫자 변환 (캐시된 매핑 사용)
    t = text
    for ko, ar in KOREAN_NUM_MAP.items():
        t = t.replace(ko, ar)
    
    # 오전/오후 판단
    am = "오전" in t
    pm = "오후" in t or "저녁" in t or "밤" in t
    
    # 사전 컴파일된 패턴들 사용
    m = PATTERNS.time_hhmm.search(t)
    if m:
        hh, mm = int(m.group(1)), int(m.group(2))
        if pm and 1 <= hh <= 11: hh += 12
        if am and hh == 12: hh = 0
        if 0 <= hh <= 23 and 0 <= mm <= 59:
            return f"{hh:02d}:{mm:02d}", 0.95
    
    m = PATTERNS.time_half.search(t)
    if m:
        hh = int(m.group(1))
        if pm and 1 <= hh <= 11: hh += 12
        if am and hh == 12: hh = 0
        if 0 <= hh <= 23:
            return f"{hh:02d}:30", 0.9
    
    m = PATTERNS.time_hour_min.search(t)
    if m:
        hh = int(m.group(1))
        mm = int(m.group(2)) if m.group(2) else 0
        if pm and 1 <= hh <= 11: hh += 12
        if am and hh == 12: hh = 0
        if 0 <= hh <= 23 and 0 <= mm <= 59:
            return f"{hh:02d}:{mm:02d}", 0.9
    
    return None, 0.0

# --- 기타 최적화된 파싱 함수들 ---
def _parse_brightness_fast(text: str) -> Tuple[Optional[int], float]:
    """최적화된 밝기 파싱"""
    # 직접 키워드 매칭 (가장 빠름)
    for keyword, level in BRIGHTNESS_LEVELS.items():
        if keyword in text:
            return level, 0.9
    
    # 퍼센트 매칭
    m = PATTERNS.brightness_percent.search(text)
    if m:
        percent = int(m.group(1))
        if 0 <= percent <= 100:
            if percent <= 12: return 0, 0.85
            elif percent <= 37: return 25, 0.85
            elif percent <= 62: return 50, 0.85
            elif percent <= 87: return 75, 0.85
            else: return 100, 0.85
    
    # 단계 매칭
    m = PATTERNS.brightness_stage.search(text)
    if m:
        stage = int(m.group(1))
        return stage * 25, 0.9
    
    return None, 0.0

# --- 2단계 시스템용 메인 인텐트 인식 함수 ---
def intent_recognize_wake_word(text: str) -> Dict[str, Any]:
    """
    Wake word 전용 인식 (2단계 시스템 1단계)
    순수한 Wake word만 감지하고 명령어는 거부
    """
    start_time = time.time()
    raw_text = text
    normalized_text = _normalize_cached(text)
    
    # Wake word 체크
    has_wake_word, wake_confidence = check_wake_word_strict(normalized_text)
    
    if not has_wake_word:
        return {
            "success": False,
            "error": "Wake word not detected",
            "confidence": 0.0,
            "processing_time": time.time() - start_time,
            "stage": "wake_word_detection"
        }
    
    # 순수한 Wake word인지 확인 (명령어가 섞여있으면 거부)
    if not is_pure_wake_word(normalized_text):
        return {
            "success": False,
            "error": "Mixed wake word and command detected. Please say wake word first",
            "confidence": wake_confidence * 0.5,
            "processing_time": time.time() - start_time,
            "stage": "wake_word_validation"
        }
    
    return {
        "success": True,
        "category": "wake_word",
        "command": "wake_detected",
        "confidence": wake_confidence,
        "processing_time": time.time() - start_time,
        "parsed_text": raw_text,
        "stage": "wake_word_detection"
    }

def intent_recognize_command(text: str) -> Dict[str, Any]:
    """
    명령어 전용 인식 (2단계 시스템 2단계)
    Wake word 없이 명령어만 처리
    """
    start_time = time.time()
    raw_text = text
    normalized_text = _normalize_cached(text)
    
    # 루틴 설정 우선 처리 (최적화된 키워드 체크)
    routine_keywords = {
        "기상", "기상시간", "깨워", "깨워줘", "알람", "알림", "일어나"
    }
    
    text_words = set(normalized_text.split())
    if routine_keywords & text_words:
        time_str, time_conf = _parse_time_ko_fast(normalized_text)
        
        if time_str:
            # 간단한 날짜 파싱 (최적화)
            offset_days = 0
            if "내일" in normalized_text:
                offset_days = 1
            elif "모레" in normalized_text:
                offset_days = 2
            
            payload = {
                "time": time_str,
                "ampm": "am" if "오전" in normalized_text else ("pm" if any(w in normalized_text for w in ["오후","저녁","밤"]) else "unknown"),
                "offset_days": offset_days,
                "date": None
            }
            
            return {
                "success": True,
                "category": "routine_setting",
                "command": "set_wake_time",
                "payload": payload,
                "confidence": time_conf,
                "processing_time": time.time() - start_time,
                "parsed_text": raw_text,
                "stage": "command_processing"
            }
    
    # 스누즈 체크
    snooze_words = {"늦춰","미뤄","미루","스누즈","10분만","십분만"}
    if snooze_words & text_words:
        return {
            "success": True,
            "category": "routine_setting",
            "command": "snooze_wake", 
            "payload": {"offset_min": 10},
            "confidence": 0.9,
            "processing_time": time.time() - start_time,
            "parsed_text": raw_text,
            "stage": "command_processing"
        }
    
    # 디바이스 제어
    device_type, device_conf = _find_device_cached(normalized_text)
    if not device_type:
        return {
            "success": False,
            "error": "Unsupported device or no device command found",
            "confidence": 0.0,
            "processing_time": time.time() - start_time,
            "stage": "device_detection"
        }
    
    # 파라미터 파싱 (병렬적으로 수행 가능)
    parsed_params = {}
    confidences = [device_conf]
    
    # 전원 상태
    power, power_conf = _parse_power_fast(normalized_text, device_type)
    if power:
        parsed_params['power'] = power
        confidences.append(power_conf)
    
    # 디바이스별 파라미터 (조건부 실행으로 최적화)
    if device_type == "air_conditioner":
        temp, temp_conf = _parse_temperature_fast(normalized_text)
        if temp is not None:
            parsed_params['temperature'] = temp
            confidences.append(temp_conf)
        
        # 모드 파싱 (빠른 검색)
        for keyword, mode in AC_MODES.items():
            if keyword in normalized_text:
                parsed_params['mode'] = mode
                confidences.append(0.85)
                break
        
        payload = {k: v for k, v in [
            ('ac_power', parsed_params.get('power')),
            ('target_ac_temperature', parsed_params.get('temperature')),
            ('target_ac_mode', parsed_params.get('mode'))
        ] if v is not None}
    
    elif device_type == "air_purifier":
        # PM 레벨
        m = PATTERNS.pm_level.search(normalized_text)
        if m:
            pm_level = float(m.group(1))
            if 1.0 <= pm_level <= 100.0:
                parsed_params['pm_level'] = pm_level
                confidences.append(0.8)
        
        # 모드
        for keyword, mode in AP_MODES.items():
            if keyword in normalized_text:
                parsed_params['mode'] = mode
                confidences.append(0.85)
                break
        
        payload = {k: v for k, v in [
            ('ap_power', parsed_params.get('power')),
            ('target_ap_pm', parsed_params.get('pm_level')),
            ('target_ap_mode', parsed_params.get('mode'))
        ] if v is not None}
    
    elif device_type == "smart_light":
        # 밝기
        brightness, brightness_conf = _parse_brightness_fast(normalized_text)
        if brightness is not None:
            parsed_params['brightness'] = brightness
            confidences.append(brightness_conf)
        
        # 색온도
        for keyword, kelvin in CCT_MAP.items():
            if keyword in normalized_text:
                parsed_params['cct'] = kelvin
                confidences.append(0.85)
                break
        
        payload = {k: v for k, v in [
            ('light_power', parsed_params.get('power')),
            ('light_temperature', parsed_params.get('cct')),
            ('target_light_level', parsed_params.get('brightness'))
        ] if v is not None}
    
    elif device_type == "smart_curtain":
        payload = {}
        if 'power' in parsed_params:
            payload['curtain'] = parsed_params['power']
    
    # 결과 반환
    if not payload:
        return {
            "success": False,
            "error": f"No valid parameters found for {device_type}",
            "confidence": max(confidences) * 0.3,
            "processing_time": time.time() - start_time,
            "stage": "parameter_parsing"
        }
    
    return {
        "success": True,
        "category": "device_control",
        "device_type": device_type,
        "payload": payload,
        "confidence": max(confidences),
        "processing_time": time.time() - start_time,
        "parsed_text": raw_text,
        "stage": "command_processing"
    }

# --- 기존 호환성을 위한 통합 함수 ---
def intent_recognize(text: str, require_wake_word: bool = True) -> Dict[str, Any]:
    """
    기존 호환성을 위한 통합 인텐트 인식 함수
    
    Args:
        text: 입력 텍스트
        require_wake_word: 시동어 필수 여부 (2단계 시스템에서는 False로 사용)
    
    Returns:
        API 형식의 응답
    """
    if require_wake_word:
        # 기존 방식: Wake word + 명령어 통합 처리
        return intent_recognize_legacy(text)
    else:
        # 2단계 시스템: 명령어만 처리
        return intent_recognize_command(text)

def intent_recognize_legacy(text: str) -> Dict[str, Any]:
    """
    기존 방식의 인텐트 인식 (하위 호환용)
    Wake word + 명령어를 한 번에 처리
    """
    start_time = time.time()
    
    raw_text = text
    normalized_text = _normalize_cached(text)
    
    # 시동어 체크
    has_wake_word, wake_confidence = check_wake_word(normalized_text)
    if not has_wake_word:
        return {
            "success": False,
            "error": "시동어가 감지되지 않았습니다",
            "confidence": 0.0,
            "processing_time": time.time() - start_time
        }
    
    # 명령어 처리 (기존 로직)
    command_result = intent_recognize_command(text)
    
    # Wake word 신뢰도와 결합
    if command_result.get("success"):
        command_result["confidence"] = min(command_result["confidence"], wake_confidence)
    
    return command_result

# --- 성능 테스트 함수 ---
def performance_test():
    """성능 테스트 (2단계 시스템용)"""
    wake_word_cases = [
        "헤이 숨",
        "숨",
        "헤이",
        "음성인식"
    ]
    
    command_cases = [
        "에어컨 켜고 24도로 맞춰줘",
        "조명 3단계로",
        "내일 7시에 깨워줘",
        "에어컨 냉방 모드",
        "커튼 열어줘"
    ]
    
    print("=== 2단계 시스템 성능 테스트 ===")
    
    print("\n--- Wake Word 테스트 ---")
    total_time = 0
    for i, test in enumerate(wake_word_cases):
        start = time.time()
        result = intent_recognize_wake_word(test)
        end = time.time()
        
        processing_time = end - start
        total_time += processing_time
        
        print(f"{i+1}. '{test}'")
        print(f"   처리시간: {processing_time*1000:.2f}ms")
        print(f"   성공: {result['success']}")
        print(f"   신뢰도: {result.get('confidence', 0):.2f}")
        print()
    
    print(f"Wake Word 평균 처리시간: {(total_time/len(wake_word_cases))*1000:.2f}ms")
    
    print("\n--- Command 테스트 ---")
    total_time = 0
    for i, test in enumerate(command_cases):
        start = time.time()
        result = intent_recognize_command(test)
        end = time.time()
        
        processing_time = end - start
        total_time += processing_time
        
        print(f"{i+1}. '{test}'")
        print(f"   처리시간: {processing_time*1000:.2f}ms")
        print(f"   성공: {result['success']}")
        print(f"   신뢰도: {result.get('confidence', 0):.2f}")
        print()
    
    print(f"Command 평균 처리시간: {(total_time/len(command_cases))*1000:.2f}ms")

if __name__ == "__main__":
    # 2단계 시스템 테스트
    print("=== 2단계 대화형 시스템 테스트 ===")
    
    print("\n1. Wake Word 테스트")
    wake_tests = [
        ("헤이 숨", True),
        ("숨", True),
        ("헤이", True),
        ("에어컨 켜줘", False),  # 명령어만 있으면 실패
        ("숨 에어컨 켜줘", False),  # 섞여있으면 실패
    ]
    
    for text, expected in wake_tests:
        result = intent_recognize_wake_word(text)
        success = result.get('success', False)
        
        status = "✅" if success == expected else "❌"
        print(f"{status} '{text}' → 성공: {success} (예상: {expected})")
        
        if success != expected:
            print(f"   오류: {result.get('error', 'N/A')}")
    
    print("\n2. Command 테스트")
    command_tests = [
        ("에어컨 켜줘", True),
        ("조명 밝게 해줘", True),
        ("내일 7시에 깨워줘", True),
        ("아무말", False),
    ]
    
    for text, expected in command_tests:
        result = intent_recognize_command(text)
        success = result.get('success', False)
        
        status = "✅" if success == expected else "❌"
        print(f"{status} '{text}' → 성공: {success} (예상: {expected})")
        
        if success != expected:
            print(f"   오류: {result.get('error', 'N/A')}")
    
    print("\n" + "="*50)
    performance_test()
