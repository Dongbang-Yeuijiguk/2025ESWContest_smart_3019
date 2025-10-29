# utils/signal_processing.py
import numpy as np
import pandas as pd
import ast
import pywt
from sklearn.decomposition import PCA
from scipy.fft import rfft, rfftfreq

# --- 1. 진폭/위상 추출 (from extract.py) ---
def amp_phase_from_csi(data, column='data'):
    if isinstance(data, pd.DataFrame):
        s = data[column]
    else:
        s = data
    N = len(s)
    AmpCSI = np.zeros((N, 64), dtype=np.float64)
    PhaseCSI = np.zeros((N, 64), dtype=np.float64)
    for i in range(N):
        item = s.iat[i]
        if pd.isna(item): continue
        if isinstance(item, str): values = ast.literal_eval(item.strip())
        else: values = list(item)
        if len(values) < 128: raise ValueError(f"[row {i}] 값이 128개 미만")
        values = values[:128]
        ImCSI = np.asarray(values[::2], dtype=np.int64)
        ReCSI = np.asarray(values[1::2], dtype=np.int64)
        AmpCSI[i, :] = np.hypot(ImCSI, ReCSI)
        PhaseCSI[i, :] = np.arctan2(ImCSI, ReCSI)
    Amp = np.concatenate([AmpCSI[:, 6:32], AmpCSI[:, 33:59]], axis=1)
    Pha = np.concatenate([PhaseCSI[:, 6:32], PhaseCSI[:, 33:59]], axis=1)
    return Amp, Pha

# --- 2. 노이즈 제거 (from noise_filtering.py) ---
def dwt_denoise_matrix(X, wavelet="db4", level=None, **kwargs):
    X = np.asarray(X, dtype=float)
    T, Ns = X.shape
    out = np.empty_like(X)
    for k in range(Ns):
        out[:, k] = _dwt_denoise_1d(X[:, k], wavelet=wavelet, level=level, **kwargs)
    return out

def _dwt_denoise_1d(x, wavelet, level, **kwargs):
    x, n = np.asarray(x, dtype=float), x.size
    w = pywt.Wavelet(wavelet)
    if level is None: level = max(1, pywt.dwt_max_level(n, w.dec_len))
    coeffs = pywt.wavedec(x, wavelet=w, mode=kwargs.get("mode", "symmetric"), level=level)
    A, Ds = coeffs[0], coeffs[1:]
    base_tau = _universal_threshold(Ds[-1], n)
    new_Ds = []
    for i, D in enumerate(Ds):
        scale_power = (len(Ds) - 1) - i
        tau = base_tau * (kwargs.get("per_level_scale", 0.85) ** scale_power)
        D_shrunk = np.sign(D) * np.maximum(np.abs(D) - tau, 0.0)
        new_Ds.append(D_shrunk)
    new_coeffs = [A] + new_Ds
    x_denoised = pywt.waverec(new_coeffs, wavelet=w, mode=kwargs.get("mode", "symmetric"))
    return x_denoised[:n]

def _universal_threshold(detail_coeffs, n):
    sigma = np.median(np.abs(detail_coeffs - np.median(detail_coeffs))) / 0.6745
    return sigma * np.sqrt(2 * np.log(n))

# --- 3. 정규화 (Standardization) ---
def standardize_matrix(data: np.ndarray) -> np.ndarray:
    """(T, F) 형태의 데이터에 대해 각 특징(F)별로 표준화를 수행합니다."""
    mean = np.mean(data, axis=0)
    std = np.std(data, axis=0)
    # 표준편차가 0인 경우를 대비하여 1e-8 더하기
    return (data - mean) / (std + 1e-8)

# --- 4. 차원 축소 (from pca.py) ---
def pca_52_subcarriers(data, n_components=1):
    if data.shape[-1] != 52: raise ValueError(f"마지막 차원은 52여야 합니다. 현재: {data.shape[-1]}")
    pca = PCA(n_components=n_components)
    return pca.fit_transform(data)

# --- 5. 저역 통과 필터 (from fft_filter.py) ---
def fft_lowpass_filter(data_1d, cutoff_freq_ratio=0.05):
    if data_1d.ndim != 1: data_1d = data_1d.flatten()
    T = data_1d.shape[0]
    data_fft = np.fft.fft(data_1d)
    cutoff_index = int(T * cutoff_freq_ratio)
    mask = np.zeros(T, dtype=bool)
    mask[:cutoff_index] = True
    mask[T - cutoff_index:] = True
    data_fft_filtered = data_fft * mask
    return np.real(np.fft.ifft(data_fft_filtered))

# --- BPM 계산 ---
def calculate_bpm_from_signal(
    signal_1d: np.ndarray,
    sampling_rate: float,
    min_freq: float = 0.1, # 6 BPM
    max_freq: float = 0.5, # 30 BPM
) -> dict:
    """
    1차원 시계열 신호에 FFT를 적용하여 주파수 대역 내 피크를 찾아 BPM을 계산합니다.

    Args:
        signal_1d (np.ndarray): 전처리가 완료된 1차원 신호.
        sampling_rate (float): 신호의 샘플링 속도 (Hz).
        min_freq (float): 탐색할 최소 주파수 (Hz).
        max_freq (float): 탐색할 최대 주파수 (Hz).

    Returns:
        dict: 계산된 BPM, 신뢰도, 성공 여부를 담은 딕셔너리.
    """
    n = len(signal_1d)
    if n == 0:
        return {"bpm": 0, "bpm_conf": 0, "ok": False}

    # FFT 수행
    yf = rfft(signal_1d)
    xf = rfftfreq(n, 1 / sampling_rate)
    
    # 크기 스펙트럼
    yf_abs = np.abs(yf)
    
    # 유효 주파수 대역 마스크 생성
    freq_mask = (xf >= min_freq) & (xf <= max_freq)
    
    if not np.any(freq_mask):
        return {"bpm": 0, "bpm_conf": 0, "ok": False}

    # 마스크 적용
    masked_freqs = xf[freq_mask]
    masked_magnitudes = yf_abs[freq_mask]
    
    if len(masked_magnitudes) == 0:
        return {"bpm": 0, "bpm_conf": 0, "ok": False}

    # 피크 주파수 탐색
    peak_index = np.argmax(masked_magnitudes)
    dominant_freq = masked_freqs[peak_index]
    
    # BPM 계산
    bpm = dominant_freq * 60
    
    # 신뢰도 계산 (간단한 방식: 전체 에너지 중 피크 에너지가 차지하는 비율)
    peak_energy = masked_magnitudes[peak_index]
    total_energy_in_range = np.sum(masked_magnitudes)
    confidence = peak_energy / total_energy_in_range if total_energy_in_range > 0 else 0
    
    return {"bpm": bpm, "bpm_conf": confidence, "ok": True}