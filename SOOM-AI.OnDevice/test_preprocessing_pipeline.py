# test_preprocessing_pipeline.py
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import argparse
import sys

# config 파일과 utils 폴더의 모듈들을 가져옵니다.
try:
    import config
    from utils.rt_preprocess import RealtimePreprocessor
    from utils.signal_processing import amp_phase_from_csi, calculate_bpm_from_signal
except ImportError as e:
    print(f"오류: 필요한 모듈을 찾을 수 없습니다. ({e})")
    print("이 스크립트가 프로젝트 최상위 폴더에 있는지, __init__.py 파일들이 각 폴더에 있는지 확인하세요.")
    sys.exit(1)

def test_pipeline(csv_file_path: str):
    """
    CSV 파일을 입력받아 전체 전처리 및 BPM 계산 파이프라인을 테스트하고 결과를 시각화합니다.
    """
    print("=" * 50)
    print(f"테스트 시작: {csv_file_path}")
    print("=" * 50)

    # --- 1. 데이터 로드 ---
    try:
        print("[1/5] CSV 데이터 로딩 중...")
        raw_df = pd.read_csv(csv_file_path)
        print(f"  ▶ 로드 완료: {raw_df.shape}")
    except FileNotFoundError:
        print(f"❌ 오류: 파일을 찾을 수 없습니다 -> {csv_file_path}")
        return
    except Exception as e:
        print(f"❌ 오류: CSV 파일 읽기 실패 - {e}")
        return

    # --- 2. 진폭 추출 ---
    try:
        print("[2/5] CSI 진폭 추출 중...")
        csi_amplitude, _ = amp_phase_from_csi(raw_df, column='data')
        print(f"  ▶ 추출 완료: {csi_amplitude.shape}")
    except Exception as e:
        print(f"❌ 오류: 진폭 추출 실패 - {e}")
        return

    # --- 3. 전처리 실행 ---
    print("[3/5] 전체 전처리 파이프라인 실행 중...")
    # config 파일의 파라미터를 사용하여 전처리기 초기화
    preprocessor = RealtimePreprocessor(
        pca_components=config.PCA_COMPONENTS,
        filter_ratio=config.FILTER_RATIO
    )
    # 진폭 데이터를 입력으로 전처리 실행
    processed_signal = preprocessor.run(csi_amplitude, model_input_size=config.WINDOW_SIZE)
    print(f"  ▶ 전처리 완료. 최종 신호 형태: {processed_signal.shape}")

    # --- 4. BPM 계산 ---
    print("[4/5] BPM 계산 중...")
    bpm_result = calculate_bpm_from_signal(
        processed_signal,
        sampling_rate=config.SAMPLING_RATE,
        min_freq=config.BPM_MIN_FREQ,
        max_freq=config.BPM_MAX_FREQ
    )
    print(f"  ▶ BPM 계산 완료: {bpm_result}")

    # --- 5. 결과 시각화 ---
    print("[5/5] 결과 시각화 중...")
    fig, axs = plt.subplots(2, 1, figsize=(15, 8), sharex=True)
    
    # 그래프 1: 처리 전 신호 (첫 번째 서브캐리어 예시)
    axs[0].plot(csi_amplitude[:, 0], label="Raw Signal (1st Subcarrier)", color='gray', alpha=0.8)
    axs[0].set_title("Before Preprocessing")
    axs[0].set_ylabel("Amplitude")
    axs[0].legend()
    axs[0].grid(True)
    
    # 그래프 2: 처리 후 신호
    axs[1].plot(processed_signal, label="Final Processed Signal", color='blue', linewidth=2)
    axs[1].set_title("After Preprocessing")
    axs[1].set_xlabel("Time (samples)")
    axs[1].set_ylabel("Amplitude")
    axs[1].legend()
    axs[1].grid(True)
    
    # 전체 제목에 BPM 결과 표시
    bpm_val = bpm_result.get('bpm', 0)
    conf_val = bpm_result.get('bpm_conf', 0)
    fig.suptitle(f"Preprocessing Pipeline Test Result\nCalculated BPM: {bpm_val:.2f} (Confidence: {conf_val:.2f})", fontsize=16)
    
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.show()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="CSI CSV 파일을 이용해 전체 전처리 및 BPM 계산 파이프라인을 테스트합니다."
    )
    parser.add_argument(
        "input_file",
        type=str,
        help="테스트할 입력 CSV 파일의 경로"
    )
    args = parser.parse_args()
    
    test_pipeline(args.input_file)