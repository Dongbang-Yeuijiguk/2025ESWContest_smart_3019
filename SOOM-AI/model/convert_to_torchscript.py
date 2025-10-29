# model/convert_to_torchscript.py (최종 수정본)
import torch
import sys
from model.classifier import Simple1DCNN # 🧩 모델 구조를 불러옵니다!

# 이 스크립트는 모델 구조와 state_dict를 결합하여 TorchScript 모델을 생성합니다.
# 사용법: python3 -m model.convert_to_torchscript <클래스 개수> <입력 길이>
# 예시:   python3 -m model.convert_to_torchscript 7 240

if len(sys.argv) != 3:
    print("❌ 사용법: python3 -m model.convert_to_torchscript <클래스 개수> <입력 길이>")
    sys.exit(1)

NUM_CLASSES = int(sys.argv[1])
INPUT_LENGTH = int(sys.argv[2])
PT_MODEL_PATH = "/home/kwonnahyun/SOOM-AI/model/best.pt"
OUTPUT_PATH = "/home/kwonnahyun/SOOM-AI/model/best_traced.pt"

print("1. 빈 모델 구조 생성 중...")
# 1. 모델의 '뼈대'를 __init__ 인자와 함께 생성합니다.
model = Simple1DCNN(num_classes=NUM_CLASSES, input_length=INPUT_LENGTH)
print(f"2. 가중치 파일 로딩 중: {PT_MODEL_PATH}")
# 2. 뼈대에 가중치(state_dict)를 입힙니다.

# --- 여기가 수정된 부분 ---
checkpoint = torch.load(PT_MODEL_PATH, map_location='cpu')
model.load_state_dict(checkpoint['model_state']) # <-- ['model_state'] 추가!
# ------------------------
model.eval()

print("3. TorchScript 모델로 변환 중...")
# 3. 모델의 입력 길이에 맞는 더미 입력을 준비합니다.

# --- 여기가 수정된 부분 ---
# (변경 전) dummy_input = torch.randn(1, INPUT_LENGTH, 1)
# (변경 후) 채널과 길이를 올바른 순서로 변경
dummy_input = torch.randn(1, 1, INPUT_LENGTH) # Shape: (1, 1, 240)
# ------------------------

# 4. 완성된 모델을 TorchScript 형식으로 변환하여 저장합니다.
traced_model = torch.jit.trace(model, dummy_input)

traced_model.save(OUTPUT_PATH)

print("\n" + "="*50)
print(f"✅ TorchScript 모델 저장 완료!")
print(f"   - 저장 경로: {OUTPUT_PATH}")
print("="*50)