# cal_bpm.py

import numpy as np
from scipy.fft import rfft, rfftfreq
import argparse

def calculate_bpm(
    file_path: str,
    sampling_rate: float,
    min_bpm: float,
    max_bpm: float
) -> float | None:
    """
    .npy 파일에서 시계열 데이터를 로드하여 FFT를 통해 BPM을 계산합니다.

    Args:
        file_path (str): 입력 .npy 파일 경로.
        sampling_rate (float): 데이터의 샘플링 주파수 (Hz).
        min_bpm (float): 탐색할 최소 BPM.
        max_bpm (float): 탐색할 최대 BPM.

    Returns:
        float | None: 계산된 BPM 값. 오류 발생 시 None 반환.
    """
    # 1. 데이터 로드
    try:
        signal = np.load(file_path)
        # 데이터는 1차원 배열이어야 함
        if signal.ndim != 1:
            print(f"오류: 입력 데이터는 1차원 배열이어야 합니다. 현재 차원: {signal.ndim}")
            return None
        print(f"✅ 데이터 로드 완료: 총 {len(signal)}개의 샘플")
    except FileNotFoundError:
        print(f"오류: 파일을 찾을 수 없습니다 -> {file_path}")
        return None
    except Exception as e:
        print(f"오류: 파일 로드 중 문제 발생 -> {e}")
        return None

    # 2. FFT 수행
    N = len(signal)
    # 실수 신호이므로 rfft 사용 (더 효율적)
    yf = rfft(signal)
    xf = rfftfreq(N, 1 / sampling_rate)
    
    # 3. 유효 BPM 범위 내에서 피크 주파수 탐색
    min_freq = min_bpm / 60.0
    max_freq = max_bpm / 60.0

    # 유효 주파수 대역에 대한 마스크 생성
    freq_mask = (xf >= min_freq) & (xf <= max_freq)
    
    if not np.any(freq_mask):
        print("오류: 지정된 BPM 범위에 해당하는 주파수 성분이 없습니다.")
        print("샘플링 속도(fs)나 데이터 길이를 확인해주세요.")
        return None

    # 마스크를 적용하여 해당 주파수와 FFT 크기 필터링
    masked_freqs = xf[freq_mask]
    masked_magnitudes = np.abs(yf[freq_mask])

    # 가장 큰 FFT 크기를 가진 주파수 탐색
    peak_index = np.argmax(masked_magnitudes)
    dominant_freq = masked_freqs[peak_index]
    
    print(f"✅ 탐지된 주요 주파수: {dominant_freq:.2f} Hz")

    # 4. BPM 계산
    bpm = dominant_freq * 60
    return bpm


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="FFT를 사용하여 .npy 파일의 시계열 데이터로부터 BPM을 계산합니다."
    )
    parser.add_argument(
        "input_file",
        type=str,
        help="입력 .npy 파일의 경로"
    )
    parser.add_argument(
        "--fs",
        type=float,
        default=60.0,
        help="신호의 샘플링 주파수(Hz). 기본값: 600.0"
    )
    parser.add_argument(
        "--min-bpm",
        type=float,
        default=0.0,
        help="탐색할 최소 BPM. 기본값: 00.0"
    )
    parser.add_argument(
        "--max-bpm",
        type=float,
        default=30.0,
        help="탐색할 최대 BPM. 기본값: 30.0"
    )

    args = parser.parse_args()

    result_bpm = calculate_bpm(
        file_path=args.input_file,
        sampling_rate=args.fs,
        min_bpm=args.min_bpm,
        max_bpm=args.max_bpm
    )

    if result_bpm is not None:
        print("-" * 30)
        print(f"🚀 최종 계산된 BPM: {result_bpm:.2f}")
        print("-" * 30)