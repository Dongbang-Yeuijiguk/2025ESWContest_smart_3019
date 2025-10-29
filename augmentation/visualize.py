# augmentation/visualize.py
"""
증강된 1D 시계열(.npy) 시각화 스크립트 (수정 버전)

- 입력: augmented_data/<label>/*.npy
- 원본: orig_data/<label>/*.npy
- 출력: viz/<label>/*.png

사용 예:
    # 기본 경로로 실행
    python visualize.py --plot-original --max-per-label 30
    
    # 특정 폴더 지정
    python visualize.py --aug-dir augmented_data --data-dir orig_data --out-dir viz_results
"""

from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import math
import random
import shutil
from typing import List, Optional


def find_labels(aug_dir: Path, specified: Optional[List[str]]) -> List[str]:
    if specified:
        return specified
    labels = sorted([p.name for p in aug_dir.iterdir() if p.is_dir()])
    return labels


def list_aug_files(aug_dir: Path, label: str) -> List[Path]:
    p = aug_dir / label
    return sorted(p.glob("*.npy"))


def load_original(data_dir: Path, label: str) -> Optional[np.ndarray]:
    """
    orig_data/<label>/ 폴더 안의 첫 번째 .npy 파일을 원본으로 로드합니다.
    """
    orig_label_dir = data_dir / label
    if not orig_label_dir.is_dir():
        return None
    
    # 폴더 내의 첫 번째 .npy 파일을 대표 원본으로 사용
    try:
        first_orig_file = next(orig_label_dir.glob("*.npy"))
        x = np.load(first_orig_file)
        if isinstance(x, np.ndarray) and x.ndim == 1:
            return x
    except StopIteration: # 파일이 없는 경우
        return None
    return None


def ensure_out_dirs(out_dir: Path, label: str) -> Path:
    target = out_dir / label
    target.mkdir(parents=True, exist_ok=True)
    return target


def plot_series(y: np.ndarray, save_path: Path, title: str,
                original: Optional[np.ndarray] = None, dpi: int = 150) -> None:
    plt.figure(figsize=(10, 3))
    plt.plot(y, linewidth=1.0, label="Augmented")
    if original is not None:
        plt.plot(original, linewidth=1.0, alpha=0.7, label="Original (Sample)", linestyle='--')
        plt.legend(loc="upper right")

    plt.title(title)
    plt.xlabel("Time")
    plt.ylabel("Amplitude")
    plt.tight_layout()
    plt.savefig(save_path, dpi=dpi)
    plt.close()


def grid_montage(sample_paths: List[Path], save_path: Path, grid_n: int, dpi: int = 150) -> None:
    n = min(len(sample_paths), grid_n)
    if n == 0: return
    cols = int(math.ceil(math.sqrt(n)))
    rows = int(math.ceil(n / cols))
    fig, axs = plt.subplots(rows, cols, figsize=(3.5 * cols, 2.2 * rows))
    axs = np.ravel(axs) # axs를 1차원 배열로 만들어 쉽게 인덱싱

    for i, p in enumerate(sample_paths[:n]):
        y = np.load(p)
        ax = axs[i]
        ax.plot(y, linewidth=0.8)
        ax.set_title(p.stem, fontsize=9)
        ax.set_xticks([])
        ax.set_yticks([])
    
    # 남는 subplot 비활성화
    for i in range(n, len(axs)):
        axs[i].set_visible(False)

    plt.tight_layout()
    plt.savefig(save_path, dpi=dpi)
    plt.close(fig)


def run(args: argparse.Namespace) -> None:
    aug_dir = Path(args.aug_dir)
    out_dir = Path(args.out_dir)
    data_dir = Path(args.data_dir)

    if not aug_dir.exists():
        raise FileNotFoundError(f"증강 폴더가 없습니다: {aug_dir}")

    labels = find_labels(aug_dir, args.labels.split() if args.labels else None)
    if not labels:
        raise RuntimeError(f"'{aug_dir}' 하위에서 라벨 폴더를 찾지 못했습니다.")

    out_dir.mkdir(parents=True, exist_ok=True)
    random.seed(args.seed)

    for label in labels:
        files = list_aug_files(aug_dir, label)
        if not files:
            print(f"[경고] '{label}' 라벨에서 .npy 파일을 찾지 못함.")
            continue

        if len(files) > args.max_per_label:
            files = random.sample(files, args.max_per_label)

        label_out = ensure_out_dirs(out_dir, label)
        orig = load_original(data_dir, label) if args.plot_original else None
        if args.plot_original and orig is None:
            print(f"[정보] '{label}'에 대한 원본 파일을 '{data_dir/label}'에서 찾을 수 없어 오버레이를 생략합니다.")

        for p in files:
            y = np.load(p)
            save_path = label_out / f"{p.stem}.png"
            title = f"Label: {label} - Sample: {p.stem}"
            plot_series(y, save_path, title, original=orig, dpi=args.dpi)

        grid_save = label_out / f"__grid_summary_{label}.png"
        grid_montage(files, grid_save, grid_n=args.grid_size, dpi=args.dpi)

        print(f"[완료] {label}: {len(files)}개 시각화 → {label_out}")

    print(f"\n[FIN] 모든 시각화를 '{out_dir}'에 저장했습니다.")


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="증강 1D 시계열 시각화")
    p.add_argument("--aug-dir", type=str, default="augmented_data", help="증강 데이터 폴더")
    p.add_argument("--out-dir", type=str, default="visualization", help="시각화 결과 폴더")
    p.add_argument("--data-dir", type=str, default="orig_data", help="원본 데이터 폴더")
    p.add_argument("--labels", type=str, default="", help='특정 라벨만, 예: "lie stand"')
    p.add_argument("--max-per-label", type=int, default=20, help="라벨별 최대 시각화 수")
    p.add_argument("--grid-size", type=int, default=16, help="그리드 요약에 담을 개수")
    p.add_argument("--seed", type=int, default=42, help="랜덤 시드")
    p.add_argument("--dpi", type=int, default=150, help="저장 이미지 DPI")
    p.add_argument("--plot-original", action="store_true", help="원본 신호를 오버레이")
    return p


if __name__ == "__main__":
    args = build_argparser().parse_args()
    run(args)