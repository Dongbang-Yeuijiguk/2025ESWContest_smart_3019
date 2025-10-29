# utils/breathing.py
from __future__ import annotations
import numpy as np
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from scipy.signal import butter, filtfilt, welch
from utils.merge_subcarrier import mrc_pca_fuse  # ← MRC-PCA 융합 함수 사용

# ----------------------------
# (Fallback) 기본 PCA/대역통과 유틸
# ----------------------------
def _pca_1d(X: np.ndarray) -> np.ndarray:
    """(T,F)->(T,), 가장 큰 주성분 시계열."""
    Xc = X - X.mean(0, keepdims=True)
    C = (Xc.T @ Xc) / max(1, Xc.shape[0] - 1)
    _, v = np.linalg.eigh(C)
    pc1 = v[:, -1]            # F,
    s = Xc @ pc1              # (T,)
    return s.astype(np.float32)

def _bandpass(sig: np.ndarray, fs: float, lo_hz: float, hi_hz: float) -> np.ndarray:
    lo = max(1e-6, lo_hz) / (fs / 2.0)
    hi = min(hi_hz, fs / 2.0 - 1e-6) / (fs / 2.0)
    b, a = butter(2, [lo, hi], btype="bandpass")
    return filtfilt(b, a, sig).astype(np.float32)

def _quality_from_psd(f: np.ndarray, Pxx: np.ndarray, f_lo: float, f_hi: float) -> Tuple[float, float]:
    """피크 품질(SNR 유사치, 피크-대-주변비)와 피크 주파수."""
    m = (f >= f_lo) & (f <= f_hi)
    if not np.any(m):
        return 0.0, np.nan
    fz, pz = f[m], Pxx[m]
    i = int(np.argmax(pz))
    f_peak, p_peak = fz[i], pz[i]
    if len(pz) > 10:
        base = np.median(np.delete(pz, i))
    else:
        base = np.mean(pz)
    snr_like = float(p_peak / (base + 1e-12))
    return snr_like, float(f_peak)

def is_empty_window(X: np.ndarray, std_thresh: float = 1e-3) -> bool:
    """
    (T,F)에서 활동 흔적 거의 없음 판단.
    - 정규화 이후라면 표준편차 임계값을 작게 설정(기본 1e-3).
    """
    X = np.asarray(X, dtype=np.float32)
    return bool(np.nan_to_num(X.std(), nan=0.0) < std_thresh)


# ----------------------------
# 설정 / 추정기
# ----------------------------
@dataclass
class BreathingConfig:
    fs: float = 100.0                 # target_fs (실시간 윈도우 샘플링)
    bpm_lo: float = 6.0               # 0.1 Hz
    bpm_hi: float = 36.0              # 0.6 Hz
    welch_nperseg: Optional[int] = None  # None이면 자동(T 또는 8초 등)
    quality_min: float = 4.0          # SNR 유사치 최소 품질
    agg_sec: float = 30.0             # 누적 길이(권장 20~40s)

    # MRC-PCA 융합 관련
    use_mrc_pca: bool = True          # True면 mrc_pca_fuse 사용
    butter_order: int = 2             # mrc_pca_fuse 내부 BP 차수
    normalize_gains: bool = True      # 최종 gain 정규화 여부


class BreathingRateEstimator:
    """
    최근 agg_sec 구간 누적 → (MRC-PCA 융합 or PCA)로 1D 호흡 파형 생성 →
    Welch-PSD 피크로 호흡수 추정.
    """
    def __init__(self, cfg: BreathingConfig):
        self.cfg = cfg
        self._buf: Optional[np.ndarray] = None  # shape (N_total, F)
        self._maxN = int(round(cfg.agg_sec * cfg.fs))

    def push_window(self, X_win: np.ndarray) -> Dict:
        """
        X_win: (T,F) - 전처리(denoise/normalize) 완료 창.
        반환: {'ok':bool, 'bpm':float, 'conf':float, 'f_hz':float, 'reason':str, 'extra':{...}}
        """
        X = np.asarray(X_win, dtype=np.float32)

        # 0) 누적 버퍼 갱신
        self._buf = X if self._buf is None else np.concatenate([self._buf, X], axis=0)
        if self._buf.shape[0] > self._maxN:
            self._buf = self._buf[-self._maxN:, :]

        # 1) 최소 길이 체크(>= agg_sec/2 정도되면 시도)
        minN = int(0.5 * self._maxN)
        if self._buf.shape[0] < minN:
            return {"ok": False, "reason": "insufficient_history"}

        # 2) 1D 대표 호흡 파형 생성
        f_lo, f_hi = self.cfg.bpm_lo / 60.0, self.cfg.bpm_hi / 60.0
        extra = {}

        if self.cfg.use_mrc_pca:
            # MRC-PCA 융합 (이미 대역통과 포함)
            fused, gains, snr_info = mrc_pca_fuse(
                self._buf,
                fs=self.cfg.fs,
                rr_band=(f_lo, f_hi),
                welch_nperseg=self.cfg.welch_nperseg,
                butter_order=self.cfg.butter_order,
                normalize_gains=self.cfg.normalize_gains,
            )
            sb = np.asarray(fused, dtype=np.float32)  # (N,)
            extra = {
                "gains": gains.tolist(),
                "snr_per_sc": snr_info.get("snr", []).tolist() if isinstance(snr_info.get("snr", None), np.ndarray) else snr_info.get("snr"),
            }
        else:
            # Fallback: PCA → 대역통과
            s = _pca_1d(self._buf)
            sb = _bandpass(s, fs=self.cfg.fs, lo_hz=f_lo, hi_hz=f_hi)

        # 3) Welch PSD → 피크 품질/주파수
        nperseg = self.cfg.welch_nperseg or min(len(sb), int(self.cfg.fs * 8))  # 기본 8초
        f, Pxx = welch(sb, fs=self.cfg.fs, nperseg=nperseg, noverlap=nperseg // 2, scaling="density")

        q, f_peak = _quality_from_psd(f, Pxx, f_lo, f_hi)
        if not np.isfinite(f_peak):
            return {"ok": False, "reason": "no_peak"}

        bpm = float(f_peak * 60.0)
        ok = bool(q >= self.cfg.quality_min)

        result = {
            "ok": ok,
            "bpm": bpm,
            "conf": float(q),
            "f_hz": float(f_peak),
            "reason": "ok" if ok else "low_quality",
        }
        if extra:
            result["extra"] = extra
        return result
