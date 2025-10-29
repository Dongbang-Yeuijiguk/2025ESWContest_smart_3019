# utils/merge_subcarrier.py
# MRC-PCA 서브캐리어 융합

import numpy as np
from scipy import signal
from numpy.linalg import svd

def bandpass_butter(x, fs, fmin=0.1, fmax=0.5, order=2):
    nyq = 0.5 * fs
    b, a = signal.butter(order, [fmin/nyq, fmax/nyq], btype='band')
    return signal.filtfilt(b, a, x)

def snr_via_psd(x, fs, rr_band=(0.1, 0.5), nperseg=None):
    """
    SNR ≈ (호흡대역 에너지) / (상위대역 에너지)
    """
    f, Pxx = signal.welch(x, fs=fs, nperseg=nperseg)
    # 호흡대역
    m1 = (f >= rr_band[0]) & (f <= rr_band[1])
    # 노이즈 대역: 호흡 상한 초과 ~ Nyquist (DC 제외)
    m2 = (f > rr_band[1]) & (f <= fs/2 * 0.999)
    Esig = np.trapz(Pxx[m1], f[m1]) if np.any(m1) else 0.0
    Enoi = np.trapz(Pxx[m2], f[m2]) if np.any(m2) else 0.0
    # 안정화용 epsilon
    eps = 1e-12
    return Esig / (Enoi + eps), Esig, Enoi

def mrc_pca_fuse(X, fs, rr_band=(0.1, 0.5), welch_nperseg=None, butter_order=2,
                 normalize_gains=True):
    """
    MRC-PCA 서브캐리어 융합.
    Args:
        X: (T, Ns) 실수(또는 실수화된 진폭/파워) 시계열
        fs: 샘플링 주파수(Hz)
        rr_band: (fmin, fmax) 호흡 대역(Hz)
        welch_nperseg: Welch PSD 세그먼트 길이(없으면 자동)
        butter_order: 대역통과 차수
        normalize_gains: True면 최종 gain을 합=1로 정규화
    Returns:
        fused: (T,) 융합 호흡 파형
        gains: (Ns,) 최종 gain (부호 정렬 포함)
        snr_info: dict( snr, Esig, Enoi per subcarrier )
    """
    X = np.asarray(X)
    T, Ns = X.shape
    # 1) 각 서브캐리어 SNR 추정 (Welch)
    snrs = np.zeros(Ns)
    Esigs = np.zeros(Ns)
    Enois = np.zeros(Ns)
    for k in range(Ns):
        snr_k, Esig_k, Enoi_k = snr_via_psd(X[:, k], fs, rr_band, welch_nperseg)
        snrs[k], Esigs[k], Enois[k] = snr_k, Esig_k, Enoi_k

    # 2) MRC 기본 gain ~ sqrt(SNR) (RMS_signal / RMS_noise)
    base_g = np.sqrt(np.maximum(snrs, 0.0))
    # 3) 대역통과(BP) + MRC 적용(노이즈 상한 억제 목적)
    X_bp = np.empty_like(X, dtype=float)
    for k in range(Ns):
        X_bp[:, k] = bandpass_butter(X[:, k] * base_g[k], fs, rr_band[0], rr_band[1], order=butter_order)

    # 4) PCA로 방향(부호) 정렬
    #  - 열(서브캐리어)별 평균 제거(공분산 안정화)
    Xc = X_bp - X_bp.mean(axis=0, keepdims=True)
    #  - SVD로 첫 주성분(loading) 추출
    #    Xc = U S V^T, 첫 로딩 벡터 v1 = V[:,0]; 부호는 임의이므로 나중에 통일
    U, S, Vt = svd(Xc, full_matrices=False)
    v1 = Vt[0, :]  # shape: (Ns,)
    sign_vec = np.sign(v1)
    sign_vec[sign_vec == 0] = 1.0  # 0이면 +로

    # 5) 최종 gain = base_g * sign(PC1 loading)
    gains = base_g * sign_vec

    if normalize_gains:
        s = np.sum(np.abs(gains)) + 1e-12
        gains = gains / s  # 합=1 (절댓값 합 기준)로 안정화

    # 6) 최종 융합: 대역통과된 원신호(부호 교정 포함)에 gains 적용
    #    (주의) 3단계에서 이미 base_g 를 곱해 BP 했으므로, 여기선 부호만 반영해서 합치거나
    #           혹은 base_g 미반영 버전을 별도로 BP 해서 gains로 합치는 두 가지가 가능함.
    #    아래는 “부호 교정 포함한 최종 gains”로 다시 가중합하는 보수적 구현:
    X_bp2 = np.empty_like(X, dtype=float)
    for k in range(Ns):
        xk_bp = bandpass_butter(X[:, k], fs, rr_band[0], rr_band[1], order=butter_order)
        X_bp2[:, k] = xk_bp

    fused = X_bp2 @ gains  # (T, Ns) @ (Ns,) -> (T,)

    # 출력 정보
    snr_info = {"snr": snrs, "Esig": Esigs, "Enoi": Enois}
    return fused, gains, snr_info
