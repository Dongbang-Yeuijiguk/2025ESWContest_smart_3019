# visualize_signal.py
import numpy as np
from scipy.fft import rfft, rfftfreq
import matplotlib.pyplot as plt
import argparse

def plot_signal_and_spectrum(
    file_path: str,
    sampling_rate: float,
    min_bpm: float,
    max_bpm: float
):
    # 1. 데이터 로드
    try:
        signal = np.load(file_path)
    except Exception as e:
        print(f"파일 로드 오류: {e}")
        return

    # 2. 시간 축 생성
    N = len(signal)
    duration = N / sampling_rate
    t = np.linspace(0, duration, N, endpoint=False)

    # 3. FFT 계산
    yf = rfft(signal)
    xf = rfftfreq(N, 1 / sampling_rate)
    yf_abs = np.abs(yf)

    # 4. BPM 계산 로직 (cal_bpm.py와 동일)
    min_freq = min_bpm / 60.0
    max_freq = max_bpm / 60.0
    freq_mask = (xf >= min_freq) & (xf <= max_freq)
    
    dominant_freq = 0
    if np.any(freq_mask):
        masked_freqs = xf[freq_mask]
        masked_magnitudes = yf_abs[freq_mask]
        if len(masked_magnitudes) > 0:
            peak_index = np.argmax(masked_magnitudes)
            dominant_freq = masked_freqs[peak_index]

    # 5. 그래프 그리기
    fig, axs = plt.subplots(2, 1, figsize=(12, 8))
    
    # 첫 번째 그래프: 시간 영역 신호
    axs[0].plot(t, signal)
    axs[0].set_title("Time Domain Signal")
    axs[0].set_xlabel("Time (s)")
    axs[0].set_ylabel("Amplitude")
    axs[0].grid(True)

    # 두 번째 그래프: 주파수 영역 스펙트럼
    axs[1].plot(xf, yf_abs)
    axs[1].set_title("Frequency Domain (FFT Spectrum)")
    axs[1].set_xlabel("Frequency (Hz)")
    axs[1].set_ylabel("Magnitude")
    # 탐색 범위 음영으로 표시
    axs[1].axvspan(min_freq, max_freq, color='orange', alpha=0.3, label=f'Search Range ({min_bpm}-{max_bpm} BPM)')
    # 탐지된 피크에 수직선 표시
    if dominant_freq > 0:
        axs[1].axvline(x=dominant_freq, color='red', linestyle='--', label=f'Detected Peak: {dominant_freq:.2f} Hz')
    
    # 0~5Hz 범위만 확대해서 보기 (일반적인 생체 신호 범위)
    axs[1].set_xlim(0, 5)
    axs[1].grid(True)
    axs[1].legend()

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Visualize signal and its FFT spectrum.")
    parser.add_argument("input_file", type=str, help="Path to the input .npy file.")
    parser.add_argument("--fs", type=float, default=60.0, help="Sampling rate in Hz.")
    parser.add_argument("--min-bpm", type=float, default=0.0, help="Minimum BPM to search.")
    parser.add_argument("--max-bpm", type=float, default=30.0, help="Maximum BPM to search.")
    
    args = parser.parse_args()
    plot_signal_and_spectrum(args.input_file, args.fs, args.min_bpm, args.max_bpm)