# utils/noise_filtering.py
# DWT 기반 신호 잡음제거

import numpy as np
import pywt

def _universal_threshold(detail_coeffs_level1: np.ndarray, n: int) -> float:
    """
    VisuShrink universal threshold:
    sigma estimated from D1 via MAD/0.6745; tau = sigma * sqrt(2*log(n)).
    """
    # sigma from MAD of level-1 details
    sigma = np.median(np.abs(detail_coeffs_level1 - np.median(detail_coeffs_level1))) / 0.6745
    tau = sigma * np.sqrt(2 * np.log(n))
    return tau

def dwt_denoise_1d(
    x: np.ndarray,
    wavelet: str = "db4",
    level: int | None = None,
    mode: str = "symmetric",
    threshold_policy: str = "universal",   # "universal" or "none"
    shrink: str = "soft",                  # "soft" or "hard"
    preserve_transients: bool = True,      # 레벨별 임계치 완화로 급격변화 보존
    per_level_scale: float = 0.85          # 레벨 올라갈수록 임계치에 곱해줄 감쇠(0.7~0.9 권장)
) -> np.ndarray:
    """
    DWT(db4) 기반 denoising. 근사계수(A)는 그대로 두고 상세계수(D)만 수축.
    preserve_transients=True이면 레벨이 높을수록(저주파 상세) 임계치를 더 낮춰
    무호흡/대동작 같은 급격한 변화를 덜 깎도록 합니다.
    """
    x = np.asarray(x, dtype=float)
    n = x.size
    w = pywt.Wavelet(wavelet)

    # 자동 레벨 선택(미지정 시)
    if level is None:
        level = pywt.dwt_max_level(n, w.dec_len)
        level = max(1, level)

    coeffs = pywt.wavedec(x, wavelet=w, mode=mode, level=level)
    # coeffs = [A_L, D_L, D_{L-1}, ..., D_1]
    A = coeffs[0]
    Ds = coeffs[1:]

    if threshold_policy == "none":
        # 아무 수축 없이 재구성
        return pywt.waverec(coeffs, wavelet=w, mode=mode)

    # universal threshold 기반 기본 임계치
    base_tau = _universal_threshold(Ds[-1], n)  # D1은 리스트의 마지막 원소

    # 상세계수에 임계치 적용
    new_Ds = []
    # enumerate with level index: Ds[0] is D_L (최고레벨, 저주파 상세), Ds[-1] is D_1 (고주파 상세)
    for i, D in enumerate(Ds):
        # 레벨 인덱스: L ... 1 (i=0 -> L, i increases -> lower level)
        # preserve_transients=True이면 레벨 높을수록(저주파) 임계치를 더 줄임
        if preserve_transients:
            # i=0(저주파 상세)일수록 감쇠 많이, i가 커질수록(고주파) 감쇠 덜
            # 예: per_level_scale^((len(Ds)-1) - i) 로 고주파에 가까울수록 scale 커짐
            scale_power = (len(Ds) - 1) - i
            tau = base_tau * (per_level_scale ** scale_power)
        else:
            tau = base_tau

        if shrink == "soft":
            D_shrunk = np.sign(D) * np.maximum(np.abs(D) - tau, 0.0)
        elif shrink == "hard":
            D_shrunk = D * (np.abs(D) >= tau)
        else:
            raise ValueError("shrink must be 'soft' or 'hard'")

        new_Ds.append(D_shrunk)

    new_coeffs = [A] + new_Ds
    x_denoised = pywt.waverec(new_coeffs, wavelet=w, mode=mode)
    # 길이 차이가 생길 수 있어 앞부분 기준으로 맞춤
    if x_denoised.size != n:
        x_denoised = x_denoised[:n]
    return x_denoised


def dwt_denoise_matrix(
    X: np.ndarray,
    wavelet: str = "db4",
    level: int | None = None,
    mode: str = "symmetric",
    threshold_policy: str = "universal",
    shrink: str = "soft",
    preserve_transients: bool = True,
    per_level_scale: float = 0.85,
    axis_time_first: bool = True,
) -> np.ndarray:
    """
    다채널(예: (T, Ns) = 시간 x 서브캐리어) CSI 신호에 대해 열(column)별 1D DWT denoise.
    """
    X = np.asarray(X, dtype=float)
    if axis_time_first:
        T, Ns = X.shape
        out = np.empty_like(X)
        for k in range(Ns):
            out[:, k] = dwt_denoise_1d(
                X[:, k],
                wavelet=wavelet,
                level=level,
                mode=mode,
                threshold_policy=threshold_policy,
                shrink=shrink,
                preserve_transients=preserve_transients,
                per_level_scale=per_level_scale,
            )
        return out
    else:
        Ns, T = X.shape
        out = np.empty_like(X)
        for k in range(Ns):
            out[k, :] = dwt_denoise_1d(
                X[k, :],
                wavelet=wavelet,
                level=level,
                mode=mode,
                threshold_policy=threshold_policy,
                shrink=shrink,
                preserve_transients=preserve_transients,
                per_level_scale=per_level_scale,
            )
        return out

