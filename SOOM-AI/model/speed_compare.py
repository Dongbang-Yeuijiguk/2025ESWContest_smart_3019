# speed_compare.py (개선된 버전)
# PyTorch(TorchScript) 모델과 TFLite 모델의 평균 추론 속도를 비교합니다.
#
# !! 중요 !!
# PyTorch 모델은 반드시 torch.jit.trace()를 사용하여 저장된
# TorchScript 모델(.pt)이어야 합니다.
#
# 사용 예시:
#   python3 -m model.speed_compare \
#       --pt-model-path "/home/kwonnahyun/SOOM-AI/model/best_traced.pt" \
#       --tflite-model-path "/home/kwonnahyun/SOOM-AI/model/movement_model.tflite" \
#       --input-shape 1 1 240



import argparse
import time
import numpy as np
import torch
import tensorflow as tf

def measure_pytorch_speed(model_path: str, input_shape: tuple, runs: int) -> float:
    """PyTorch (TorchScript) 모델의 평균 추론 시간을 측정합니다."""
    print("PyTorch (TorchScript) 모델 로딩 및 속도 측정 중...")
    try:
        # torch.jit.load()를 사용하여 모델 구조까지 한 번에 로드
        model = torch.jit.load(model_path, map_location='cpu')
        model.eval()
    except Exception as e:
        print(f"❌ PyTorch TorchScript 모델 로딩 실패: {e}")
        print("    --pt-model-path의 모델이 torch.jit.trace()로 저장되었는지 확인하세요.")
        exit(1)

    dummy_input = torch.randn(input_shape)
    
    # 예열(Warm-up)
    for _ in range(10):
        _ = model(dummy_input)

    # 실제 측정
    with torch.no_grad():
        start_time = time.perf_counter()
        for _ in range(runs):
            _ = model(dummy_input)
        end_time = time.perf_counter()

    avg_latency_ms = ((end_time - start_time) / runs) * 1000
    return avg_latency_ms

def measure_tflite_speed(model_path: str, runs: int) -> float:
    """TFLite 모델의 평균 추론 시간을 측정합니다."""
    print("TFLite 모델 속도 측정 중...")
    try:
        interpreter = tf.lite.Interpreter(model_path=model_path)
        interpreter.allocate_tensors()
    except Exception as e:
        print(f"❌ TFLite 모델 로딩 실패: {e}")
        exit(1)

    input_details = interpreter.get_input_details()
    input_shape = input_details[0]['shape']
    dummy_input = np.random.randn(*input_shape).astype(np.float32)

    # 예열(Warm-up)
    for _ in range(10):
        interpreter.set_tensor(input_details[0]['index'], dummy_input)
        interpreter.invoke()

    # 실제 측정
    start_time = time.perf_counter()
    for _ in range(runs):
        interpreter.set_tensor(input_details[0]['index'], dummy_input)
        interpreter.invoke()
    end_time = time.perf_counter()

    avg_latency_ms = ((end_time - start_time) / runs) * 1000
    return avg_latency_ms

def main():
    parser = argparse.ArgumentParser(description="PyTorch(TorchScript)와 TFLite 모델의 추론 속도를 비교합니다.")
    parser.add_argument("--pt-model-path", type=str, required=True, help="PyTorch TorchScript 모델(.pt) 경로")
    parser.add_argument("--tflite-model-path", type=str, required=True, help="TFLite 모델(.tflite) 경로")
    parser.add_argument("--input-shape", type=int, nargs='+', required=True, help="모델의 입력 형태 (예: 1 3 224 224)")
    parser.add_argument("--runs", type=int, default=10000, help="속도 측정을 위한 반복 횟수")
    args = parser.parse_args()

    # 속도 측정
    pt_latency = measure_pytorch_speed(args.pt_model_path, tuple(args.input_shape), args.runs)
    tflite_latency = measure_tflite_speed(args.tflite_model_path, args.runs)

    # 결과 출력
    print("\n" + "="*50)
    print("🚀 모델 추론 속도 비교 결과")
    print("="*50)
    print(f"  - 반복 횟수: {args.runs}회")
    print(f"  - 입력 형태: {tuple(args.input_shape)}")
    print("-"*50)
    print(f"  🔵 PyTorch 모델 : {pt_latency:.4f} ms")
    print(f"  🟢 TFLite 모델  : {tflite_latency:.4f} ms")
    print("-"*50)
    
    if pt_latency > tflite_latency:
        speed_up = pt_latency / tflite_latency
        print(f"✅ TFLite 모델이 {speed_up:.2f}배 더 빠릅니다.")
    else:
        speed_up = tflite_latency / pt_latency
        print(f"⚠️ PyTorch 모델이 {speed_up:.2f}배 더 빠릅니다.")
    print("="*50)

if __name__ == "__main__":
    main()