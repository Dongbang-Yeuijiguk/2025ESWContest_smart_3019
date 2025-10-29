# model/convert_to_tflite.py
# ONNX 모델을 TFLite로 변환하는 간단한 스크립트.
#
# 사용 예:
#   # 기본 변환 (양자화 없음)
#   python -m model.convert_to_tflite results/run1/exported/model.onnx --out model/presence_model.tflite
#
#   # Float16 양자화 적용
#   python -m model.convert_to_tflite results/run1/exported/model.onnx --out model/presence_model_fp16.tflite --quantize-fp16

import argparse
from pathlib import Path
import shutil
import tempfile
import onnx
from onnx_tf.backend import prepare
import tensorflow as tf

def convert_onnx_to_tflite(
    onnx_path: str | Path,
    out_path: str | Path,
    quantize_fp16: bool = False
):
    """
    ONNX 모델을 TFLite 모델로 변환합니다.

    Args:
        onnx_path (str | Path): 입력 ONNX 파일 경로.
        out_path (str | Path): 저장할 TFLite 파일 경로.
        quantize_fp16 (bool): Float16 양자화 적용 여부.
    """
    onnx_path = Path(onnx_path)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # --- 1. ONNX -> TensorFlow SavedModel 변환 ---
    # TensorFlow Lite 변환기는 ONNX를 직접 읽지 못하므로 중간 단계가 필요합니다.

    print(f"ONNX 파일 로드 중: {onnx_path}")
    onnx_model = onnx.load(str(onnx_path))
    
    # 임시 폴더를 사용하여 중간 단계의 SavedModel을 저장합니다.
    with tempfile.TemporaryDirectory() as temp_dir:
        saved_model_dir = Path(temp_dir)
        print(f"중간 단계(SavedModel) 저장 중: {saved_model_dir}")
        
        tf_rep = prepare(onnx_model)
        tf_rep.export_graph(str(saved_model_dir))

        # --- 2. TensorFlow SavedModel -> TFLite 변환 ---
        print("TFLite 변환 시작...")
        converter = tf.lite.TFLiteConverter.from_saved_model(str(saved_model_dir))

        # Float16 양자화 옵션 적용
        if quantize_fp16:
            print("Float16 양자화 적용 중...")
            converter.optimizations = [tf.lite.Optimize.DEFAULT]
            converter.target_spec.supported_types = [tf.float16]

        # TFLite 모델 생성
        tflite_model = converter.convert()

    # --- 3. TFLite 모델 파일로 저장 ---
    out_path.write_bytes(tflite_model)
    print("\n" + "="*50)
    print(f"✅ TFLite 변환 완료!")
    print(f"   - 원본 (ONNX): {onnx_path.name} ({onnx_path.stat().st_size / 1024:.2f} KB)")
    print(f"   - 결과 (TFLite): {out_path.name} ({len(tflite_model) / 1024:.2f} KB)")
    print(f"   - 저장 경로: {out_path.resolve()}")
    print("="*50)


def main():
    parser = argparse.ArgumentParser(description="ONNX 모델을 TFLite로 변환합니다.")
    parser.add_argument(
        "onnx_path",
        type=str,
        help="입력 ONNX 모델 파일 경로 (예: results/run1/exported/model.onnx)"
    )
    parser.add_argument(
        "--out",
        type=str,
        required=True,
        help="저장할 TFLite 파일 경로 (예: model/presence_model.tflite)"
    )
    parser.add_argument(
        "--quantize-fp16",
        action="store_true",
        help="Float16 양자화를 적용하여 모델 크기를 줄입니다."
    )
    args = parser.parse_args()

    convert_onnx_to_tflite(
        onnx_path=args.onnx_path,
        out_path=args.out,
        quantize_fp16=args.quantize_fp16
    )

if __name__ == "__main__":
    main()