# config.py

# ==============================================================================
# InfluxDB 설정 (데이터 읽기용)
# ==============================================================================
# 실시간 CSI 원본 데이터가 저장된 InfluxDB의 접속 정보
INFLUX_READ_URL = "http://13.209.47.2:8086"  # URL 형식 수정
INFLUX_READ_ORG = "sscc"
INFLUX_READ_BUCKET = "test"
INFLUX_READ_MEASUREMENT = "csi_measurement"

INFLUX_TOKEN = "=="

# ==============================================================================
# InfluxDB 설정 (결과 쓰기용)
# ==============================================================================
# AI 추론 결과와 수면 상태를 저장할 InfluxDB의 접속 정보
INFLUX_WRITE_URL = "http://13.209.47.2:8086" # URL 형식 수정
INFLUX_WRITE_ORG = "sscc"
INFLUX_WRITE_BUCKET = "test"
INFLUX_WRITE_MEASUREMENT = "inference_results"
INFLUX_STATE_MEASUREMENT = "sleep_data"


# ==============================================================================
# 실시간 파이프라인 파라미터
# ==============================================================================

SAMPLING_RATE = 60.0    # 센서 데이터 샘플링 레이트 (Hz)
WINDOW_SECONDS = 4      # 1회 추론에 사용할 데이터 창 크기 (초)
STEP_SECONDS = 3.0      # main.py 루프 주기 및 데이터 조회 간격 (초)

# 초 단위를 데이터 포인트 개수로 자동 변환
WINDOW_SIZE = int(SAMPLING_RATE * WINDOW_SECONDS) # 240
STEP_SIZE = int(SAMPLING_RATE * STEP_SECONDS)     # 180
MODEL_INPUT_SIZE = int(WINDOW_SECONDS * SAMPLING_RATE)
RAW_CSI_COLUMN = "data"

# ==============================================================================
# 모델 및 전처리 파라미터
# ==============================================================================
# --- 모델 경로 ---
MOVEMENT_MODEL_PATH = "models/movement_model.tflite"
MOVEMENT_MODEL_PATH_PT = "models/best.pt"

# --- 모델 레이블 정의 ---
# 추가된 라벨 모두 반영. 실제 학습된 모델의 라벨 순서와 정확히 일치해야 함.
MOVEMENT_LABELS = ['book', 'lie', 'phone', 'rustle', 'sit', 'stand', 'walk']
NUM_CLASSES = len(MOVEMENT_LABELS)

# --- 행동 분류 신뢰도 임계값 ---
# 모델의 예측 확률이 이 값보다 낮으면 'unknown'으로 처리합니다. (0.0 ~ 1.0)
MOVEMENT_CONFIDENCE_THRESHOLD = 0.6 # 60%

# --- 통계 기반 존재 감지 임계값 ---
# 이 값보다 분산이 크면 'present'로 판단 (test_statistical_threshold.py로 튜닝)
PRESENCE_VARIANCE_THRESHOLD = 0.0000075

# --- BPM 계산 파라미터 ---
BPM_MIN_FREQ = 0.0  # 0 BPM
BPM_MAX_FREQ = 1.0  # 60 BPM

# --- 전처리 파라미터 ---
PCA_COMPONENTS = 1
FILTER_RATIO = 0.05 # 5% 저역 통과 필터


# ==============================================================================
# 수면 상태 판단 로직 파라미터
# ==============================================================================
# 데이터를 식별하기 위한 사용자 ID
USER_ID = "USER_001"

# 'PRE_SLEEP' 상태에서 'SLEEPING' 상태로 넘어가기까지 필요한 최소 시간 (초 단위)
# 600초 = 10분
PRE_SLEEP_DURATION_THRESHOLD = 10

WAKEUP_CONFIRM_THRESHOLD = 4