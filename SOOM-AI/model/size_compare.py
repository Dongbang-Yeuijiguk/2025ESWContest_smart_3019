import os

pt_path = "/home/kwonnahyun/SOOM-AI/model/best.pt"
tflite_path = "/home/kwonnahyun/SOOM-AI/model/movement_model.tflite"

pt_size_mb = os.path.getsize(pt_path) / (1024 * 1024)
tflite_size_mb = os.path.getsize(tflite_path) / (1024 * 1024)

print(f"PyTorch 모델 크기: {pt_size_mb:.2f} MB")
print(f"TFLite 모델 크기: {tflite_size_mb:.2f} MB")