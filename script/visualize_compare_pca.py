from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
# 서버/노트북 환경에서 GUI 없이 저장만 하려면 이 설정을 유지합니다.
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from typing import Tuple, Optional
# 가정: utils.extract, utils.load 모듈은 접근 가능합니다.
from utils.extract import amp_phase_from_csi
from utils.load import load_csi_data

def load_raw_amp(csv_path: Path) -> np.ndarray:
    """
    원본 CSV -> (amp, phase) 중 amp만 사용.
    (수정) 길이 제한 없이 전체 데이터를 불러옵니다.
    """
    try:
        raw = load_csi_data(csv_path)
    except Exception as e:
        raise IOError(f"Failed to load CSI data from {csv_path}: {e}")

    amp, _ = amp_phase_from_csi(raw)
    amp = np.asarray(amp)
    if amp.ndim != 2:
        raise ValueError(f"Amplitude must be 2D (T,F). Got shape {amp.shape} from {csv_path}")

    # (수정) 길이 제한 로직을 제거하여 전체 데이터를 반환합니다.
    return amp.astype(np.float32, copy=False)

def load_preprocessed_npy(npy_path: Path) -> np.ndarray:
    """
    전처리된 .npy -> PCA 후 (T, 1) 또는 (T,) 형태를 (T,) 1차원 배열로 변환.
    """
    arr = np.load(npy_path, allow_pickle=False)
    
    # 3D (1, T, 1) -> 2D (T, 1) -> 1D (T,) 처리
    if arr.ndim == 3 and arr.shape[0] == 1:
        arr = arr[0]
        
    # 2D (T, 1) -> 1D (T,) 처리
    if arr.ndim == 2:
        if arr.shape[1] == 1:
            arr = arr[:, 0] # (T, 1) -> (T,)
        else:
            raise ValueError(f"Preprocessed 2D array must have 1 feature (T, 1). Got {arr.shape} from {npy_path}")
            
    if arr.ndim != 1:
        raise ValueError(f"Preprocessed array must be 1D (T,) after processing. Got {arr.shape} from {npy_path}")
    
    return arr.astype(np.float32, copy=False)

def compute_raw_scale(a: np.ndarray, pct_lo=1.0, pct_hi=99.0) -> Tuple[float, float]:
    """히트맵의 vmin/vmax를 주기 위해 퍼센타일 기반 스케일 계산."""
    vmin = float(np.nanpercentile(a, pct_lo))
    vmax = float(np.nanpercentile(a, pct_hi))
    if vmin == vmax:
        vmax = vmin + 1e-6
    return vmin, vmax

def plot_pair_raw_heatmap_proc_line(
    amp_raw: np.ndarray, # (T_raw, F)
    amp_proc_1d: np.ndarray, # (T_proc,)
    out_path: Path,
    title_left: str,
    title_right: str,
    cmap: str = "viridis",
    figsize: Tuple[int,int] = (14, 5)
) -> None:
    """원본(히트맵)/전처리된 1D PCA 결과(시계열) 2개 그래프를 한 장에 저장."""
    
    T_proc = amp_proc_1d.shape[0]
    T_raw = amp_raw.shape[0]
    
    if T_raw != T_proc:
        # 이 경고는 이제 거의 나타나지 않아야 합니다.
        print(f"[WARN] Time steps mismatch: Raw={T_raw}, Proc={T_proc}. X축 범위가 다를 수 있습니다.")

    # 1. 원본 히트맵을 위한 스케일 계산
    vmin, vmax = compute_raw_scale(amp_raw, 1.0, 99.0)

    fig, axes = plt.subplots(1, 2, figsize=figsize, constrained_layout=True)

    # ====== 1. 원본 데이터 (히트맵) ======
    im0 = axes[0].imshow(amp_raw.T, aspect="auto", origin="lower",
                         cmap=cmap, vmin=vmin, vmax=vmax)
    axes[0].set_title(f"{title_left}\nshape={amp_raw.shape}")
    axes[0].set_xlabel("Time index (T)")
    axes[0].set_ylabel("Subcarrier (F)")
    
    axes[0].set_xlim(-0.5, T_raw - 0.5) 

    cbar = fig.colorbar(im0, ax=axes[0], shrink=0.9, pad=0.05)
    cbar.set_label("Raw Amplitude (arbitrary)")

    # ====== 2. 전처리 데이터 (시계열) ======
    time_indices = np.arange(T_proc)
    
    axes[1].plot(time_indices, amp_proc_1d, color='blue', linewidth=1, label="PC 1")
    
    axes[1].set_title(f"{title_right}\nshape={amp_proc_1d.shape}")
    axes[1].set_xlabel("Time index (T)")
    axes[1].set_ylabel("Amplitude of Principal Component (PC)")
    axes[1].grid(True, linestyle='--', alpha=0.6)
    axes[1].legend()
    
    axes[1].set_xlim(0, T_proc - 1)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=200)
    plt.close(fig)

def find_matching_npy(preproc_root: Path, label: str, stem: str) -> Optional[Path]:
    """
    전처리 npy 파일을 찾습니다. preprocessed/<label>/<stem>.npy 를 우선 찾고, 없으면 와일드카드 탐색.
    """
    candidate = preproc_root / label / f"{stem}.npy"
    if candidate.exists():
        return candidate
    
    matches = list((preproc_root / label).glob(f"{stem}*.npy"))
    return matches[0] if matches else None

def main():
    ap = argparse.ArgumentParser(description="Visualize Raw CSI (Heatmap) vs Preprocessed 1D PCA (Line Plot) as side-by-side PNGs")
    # ap.add_argument("--dataset-root", type=str, default="../dataset", help="dataset/<label>/*.csv")
    ap.add_argument("--dataset-root", type=str, default="./data", help="dataset/<label>/*.csv")
    ap.add_argument("--preprocessed-root", type=str, default="preprocessed", help="preprocessed/<label>/*.npy (Expected to be 1D/T,1)")
    ap.add_argument("--out-root", type=str, default="viz_compare_pca_line", help="출력 PNG 루트 디렉토리")
    ap.add_argument("--cmap", type=str, default="viridis")
    ap.add_argument("--figwidth", type=int, default=14)
    ap.add_argument("--figheight", type=int, default=5)
    ap.add_argument("--max-files", type=int, default=0, help="라벨당 최대 처리 파일 수(0=제한 없음)")
    args = ap.parse_args()

    dataset_root = Path(args.dataset_root)
    preproc_root = Path(args.preprocessed_root)
    out_root = Path(args.out_root)

    labels = sorted([p.name for p in dataset_root.iterdir() if p.is_dir()])
    if not labels:
        raise SystemExit(f"No label directories under: {dataset_root}")

    total = 0
    for label in labels:
        csv_dir = dataset_root / label
        csv_files = sorted(csv_dir.glob("*.csv"))
        if args.max_files > 0:
            csv_files = csv_files[:args.max_files]

        if not csv_files:
            print(f"[WARN] No CSV files in {csv_dir}")
            continue

        for csv_path in csv_files:
            stem = csv_path.stem 
            npy_path = find_matching_npy(preproc_root, label, stem)
            if npy_path is None:
                print(f"[SKIP] No matching NPY for {label}/{stem}")
                continue

            try:
                # 1. 전체 길이의 원본 데이터를 불러옵니다.
                amp_raw = load_raw_amp(csv_path)
                amp_proc_1d = load_preprocessed_npy(npy_path)

                # 2. (수정) 전처리된 데이터 길이를 기준으로 원본과 전처리 데이터를 자릅니다. (동기화)
                T_proc = amp_proc_1d.shape[0]
                # 원본이 전처리된 것보다 짧은 예외상황을 대비해 둘 중 최소 길이를 사용합니다.
                final_T = min(amp_raw.shape[0], T_proc)
                
                amp_raw = amp_raw[:final_T, :]
                amp_proc_1d = amp_proc_1d[:final_T]

            except Exception as e:
                print(f"[ERROR] {label}/{stem}: {e}")
                continue

            out_path = out_root / label / f"{stem}.png"
            title_left = f"RAW CSI AMP (Synced) {label}/{csv_path.name}"
            title_right = f"PREPROC PCA {label}/{npy_path.name}"
            
            # 3. 길이가 보장된 데이터를 플롯 함수에 전달합니다.
            plot_pair_raw_heatmap_proc_line(
                amp_raw, amp_proc_1d, out_path,
                title_left=title_left, title_right=title_right,
                cmap=args.cmap,
                figsize=(args.figwidth, args.figheight)
            )
            total += 1
            print(f"[OK] saved {out_path}")

    print(f"[DONE] saved {total} comparison figures to {out_root}")

if __name__ == "__main__":
    main()