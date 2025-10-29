# test_windowing_pipeline.py
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import argparse
import sys
from tqdm import tqdm

try:
    import config
    from utils.rt_preprocess import RealtimePreprocessor
    from utils.signal_processing import amp_phase_from_csi, calculate_bpm_from_signal
except ImportError as e:
    print(f"오류: 필요한 모듈을 찾을 수 없습니다. ({e})")
    print("이 스크립트가 프로젝트 최상위 폴더에 있는지, __init__.py 파일들이 각 폴더에 있는지 확인하세요.")
    sys.exit(1)

def test_windowing_on_file(csv_file_path: str):
    print("=" * 50)
    print(f"슬라이딩 윈도우 테스트 시작: {csv_file_path}")
    print("=" * 50)

    # --- 1. 데이터 로드 및 진폭 추출 ---
    try:
        print("[1/4] 전체 CSV 데이터 로딩 및 진폭 추출 중...")
        raw_df = pd.read_csv(csv_file_path)
        csi_amplitude, _ = amp_phase_from_csi(raw_df, column='data')
        print(f"  ▶ 데이터 준비 완료: {csi_amplitude.shape}")
    except Exception as e:
        print(f"❌ 오류: 데이터 준비 실패 - {e}")
        return

    # --- 2. 컴포넌트 초기화 ---
    print("[2/4] 전처리기 및 파라미터 초기화 중...")
    preprocessor = RealtimePreprocessor(
        pca_components=config.PCA_COMPONENTS,
        filter_ratio=config.FILTER_RATIO
    )
    window_size = config.WINDOW_SIZE
    step_size = config.STEP_SIZE
    total_samples = csi_amplitude.shape[0]
    
    if total_samples < window_size:
        print(f"❌ 오류: 데이터 길이({total_samples})가 윈도우 크기({window_size})보다 작습니다.")
        return
        
    bpm_results = []
    print(f"  ▶ 윈도우 크기: {window_size}, 스텝 크기: {step_size}")

    # --- 3. 슬라이딩 윈도우 시뮬레이션 및 반복 계산 ---
    print("[3/4] 슬라이딩 윈도우를 통해 BPM 계산 반복 실행 중...")
    num_windows = (total_samples - window_size) // step_size + 1
    for i in tqdm(range(0, total_samples - window_size + 1, step_size), desc="Processing windows"):
        current_window_data = csi_amplitude[i : i + window_size]
        processed_signal = preprocessor.run(current_window_data, model_input_size=config.WINDOW_SIZE)
        bpm_result = calculate_bpm_from_signal(
            processed_signal,
            sampling_rate=config.SAMPLING_RATE,
            min_freq=config.BPM_MIN_FREQ,
            max_freq=config.BPM_MAX_FREQ
        )
        bpm_results.append(bpm_result.get('bpm', 0))

    print(f"  ▶ 총 {len(bpm_results)}개의 윈도우 처리 완료.")

    # --- 4. 최종 결과 시각화 ---
    print("[4/4] 결과 시각화 중...")
    fig, axs = plt.subplots(3, 1, figsize=(15, 10), sharex=False)
    
    # --- 시각화를 위한 대표 윈도우 선택 (중간 지점) ---
    mid_point_start = (total_samples - window_size) // 2
    raw_window_sample = csi_amplitude[mid_point_start : mid_point_start + window_size]
    processed_signal_sample = preprocessor.run(raw_window_sample, model_input_size=config.WINDOW_SIZE)
    
    # 그래프 1: Raw 데이터 (대표 윈도우)
    axs[0].plot(raw_window_sample[:, 0], label="Raw Signal (1st Subcarrier)", color='gray', alpha=0.9)
    axs[0].set_title(f"1. Raw Data (Sample Window from index {mid_point_start})")
    axs[0].set_ylabel("Amplitude")
    axs[0].legend()
    axs[0].grid(True)
    
    # 그래프 2: 전처리 후 데이터 (대표 윈도우)
    axs[1].plot(processed_signal_sample, label="Preprocessed Signal", color='green')
    axs[1].set_title("2. Preprocessed Data (Same Sample Window)")
    axs[1].set_xlabel("Time (samples within window)")
    axs[1].set_ylabel("Amplitude")
    axs[1].legend()
    axs[1].grid(True)

    # 그래프 3: 전체 구간에 대한 BPM 계산 결과
    time_axis = np.arange(len(bpm_results)) * config.STEP_SECONDS
    axs[2].plot(time_axis, bpm_results, label="BPM over Time", color='blue', marker='.', linestyle='-')
    axs[2].set_title("3. BPM Calculation Result over All Windows")
    axs[2].set_xlabel(f"Time (seconds={config.WINDOW_SECONDS}, step size={config.STEP_SECONDS}s)")
    axs[2].set_ylabel("Calculated BPM")
    axs[2].grid(True)
    
    # ✅ --- 수정된 부분 시작 ---
    # 대표 윈도우가 시작된 시간 계산
    # mid_point_start를 step_size로 나누어 몇 번째 윈도우인지 찾고, 시간으로 변환
    sample_window_start_time = (mid_point_start // step_size) * config.STEP_SECONDS
    sample_window_end_time = sample_window_start_time + config.WINDOW_SECONDS

    # axvspan을 사용하여 해당 시간 범위를 음영으로 표시
    axs[2].axvspan(
        sample_window_start_time, 
        sample_window_end_time, 
        color='orange', 
        alpha=0.3, 
        label='Sample Window Location'
    )
    
    axs[2].legend() # 범례를 다시 호출하여 음영 표시를 추가
    
    # 전체 제목
    avg_bpm = np.mean(bpm_results)
    std_bpm = np.std(bpm_results)
    fig.suptitle(f"Sliding Window Test Result\nAverage BPM: {avg_bpm:.2f} (Std Dev: {std_bpm:.2f})", fontsize=16)
    
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.show()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="긴 CSI CSV 파일을 슬라이딩 윈도우 방식으로 테스트하고 3개의 플롯으로 결과를 분석합니다."
    )
    parser.add_argument(
        "input_file",
        type=str,
        help="테스트할 긴 입력 CSV 파일의 경로"
    )
    args = parser.parse_args()
    
    test_windowing_on_file(args.input_file)