# model/config.py
from pathlib import Path

# --- 경로 및 기본 설정 ---
# 학습 결과가 저장될 최상위 폴더
SAVE_DIR_ROOT = Path("results/")
# 내보낸 모델(ONNX 등)이 저장될 폴더 이름
EXPORTED_MODEL_DIR_NAME = "exported"

# --- 학습 대상 설정 ---
TARGET_LABELS = ['book', 'lie', 'phone', 'rustle', 'sit', 'stand', 'walk']
NUM_CLASSES = len(TARGET_LABELS)

# --- 입력 데이터 설정 ---
SAMPLING_RATE = 60  # Hz, 입력 데이터의 샘플링 레이트
WINDOW_SECONDS = 4  # 초, 입력 데이터 윈도우 길이
INPUT_LENGTH = SAMPLING_RATE * WINDOW_SECONDS  # 입력 데이터 길이 (샘플 수)

# --- 데이터로더 설정 ---
BATCH_SIZE = 32
# 사용 가능한 CPU 코어의 절반을 사용하는 것을 권장 (None으로 두면 전부 사용)
# import os; NUM_WORKERS = os.cpu_count() // 2
NUM_WORKERS = 4

# --- 학습 하이퍼파라미터 ---
SEED = 42
EPOCHS = 100
LR = 1e-3
WEIGHT_DECAY = 1e-4
LABEL_SMOOTHING = 0.1
# 조기 종료(Early Stopping) 대기 에포크 수 (0이면 비활성화)
PATIENCE = 0
# Gradient Clipping 값 (0이면 비활성화)
GRAD_CLIP = 1.0

# --- 시스템 / 하드웨어 설정 ---
# Automatic Mixed Precision (AMP) 사용 여부. True로 두면 학습 속도 향상
USE_AMP = True
# DataParallel을 사용하여 멀티 GPU 학습 여부
USE_DATA_PARALLEL = True

# --- ONNX 내보내기 옵션 ---
ONNX_OPSET = 13
# ONNX 모델의 배치 차원을 동적으로 설정할지 여부
ONNX_DYNAMIC_BATCH = True