# augmentation/augmentation.py
"""
1D 시계열 데이터 증강 스크립트.
orig_data/<label>/*.npy 구조의 모든 파일을 읽어 기본 증강을 적용하고,
augmented_data/<label>/ 폴더에 증강된 결과들을 저장합니다.

사용 예:
  python augmentation_basic.py --count-per-file 50
"""

from __future__ import annotations
import argparse
from pathlib import Path
from typing import Tuple
import numpy as np
from numpy.typing import NDArray
from tqdm import tqdm

# ----------------------
# 기본 증강 함수들 (변경 없음)
# ----------------------
def add_gaussian_noise(x: NDArray, rng: np.random.Generator, std_frac: float) -> NDArray:
    """가우시안 노이즈 추가"""
    s = np.std(x)
    sigma = s * std_frac if s > 0 else std_frac
    return x + rng.normal(0.0, sigma, size=x.shape)

def time_scale_and_resample(x: NDArray, scale: float) -> NDArray:
    """시간 축 스케일링 후 원래 길이로 리샘플링"""
    N = len(x)
    if N < 2: return x.copy()
    new_len = max(2, int(round(N * scale)))
    old_idx, new_idx = np.linspace(0, N - 1, num=N), np.linspace(0, N - 1, num=new_len)
    x_scaled = np.interp(new_idx, old_idx, x)
    back_idx = np.linspace(0, new_len - 1, num=N)
    return np.interp(back_idx, np.arange(new_len), x_scaled)

def amp_scale(x: NDArray, scale: float) -> NDArray:
    """진폭 스케일링"""
    return x * scale

# ----------------------
# 샘플 하나 증강 (변경 없음)
# ----------------------
def augment_once(
    x: NDArray, rng: np.random.Generator,
    noise_std_range: Tuple[float, float],
    time_scale_range: Tuple[float, float],
    amp_scale_range: Tuple[float, float],
) -> NDArray:
    """하나의 1D 시계열 데이터에 대해 기본 증강 기법들을 랜덤하게 조합하여 적용합니다."""
    y = x.copy()
    if rng.random() < 0.9: y = time_scale_and_resample(y, rng.uniform(*time_scale_range))
    if rng.random() < 0.9: y = amp_scale(y, rng.uniform(*amp_scale_range))
    if rng.random() < 0.9: y = add_gaussian_noise(y, rng, rng.uniform(*noise_std_range))
    return y

# ----------------------
# IO & 메인 파이프라인 (수정됨)
# ----------------------
def save_augmented_series(series: NDArray, out_dir: Path, prefix: str, idx: int) -> None:
    """증강된 데이터를 .npy 파일로 저장합니다."""
    out_path = out_dir / f"{prefix}_aug_{idx:04d}.npy"
    np.save(out_path, series)

def run(args: argparse.Namespace) -> None:
    """메인 실행 함수"""
    data_dir = Path(args.data_dir)
    out_dir = Path(args.out_dir)

    # data 디렉토리 아래의 모든 하위 폴더(레이블)를 찾습니다.
    label_dirs = [d for d in data_dir.iterdir() if d.is_dir()]
    if not label_dirs:
        print(f"❌ 오류: '{data_dir}' 폴더에서 레이블 폴더를 찾을 수 없습니다.")
        return

    print(f"총 {len(label_dirs)}개의 레이블 폴더를 찾았습니다: {[d.name for d in label_dirs]}")

    rng = np.random.default_rng(args.seed)
    noise_range = (args.noise_std_min, args.noise_std_max)
    time_range = (args.time_scale_min, args.time_scale_max)
    amp_range = (args.amp_scale_min, args.amp_scale_max)

    # 각 레이블 폴더에 대해 증강을 수행합니다.
    for label_path in tqdm(label_dirs, desc="Processing Labels"):
        label = label_path.name
        
        # 출력 폴더 생성 (예: augmented_data/lie/)
        label_out_dir = out_dir / label
        label_out_dir.mkdir(parents=True, exist_ok=True)
        
        input_files = list(label_path.glob("*.npy"))
        if not input_files:
            print(f"⚠️  경고: '{label}' 폴더에 .npy 파일이 없습니다. 건너뜁니다.")
            continue
            
        augmented_file_counter = 0
        # 해당 레이블 폴더 안의 모든 파일에 대해 증강 수행
        for file_path in tqdm(input_files, desc=f"  Augmenting '{label}'", leave=False):
            try:
                x = np.load(file_path)
                if x.ndim != 1:
                    print(f"⚠️ 경고: 1D 데이터가 아닌 파일은 건너뜁니다. ({file_path.name})")
                    continue
            except Exception as e:
                print(f"⚠️ 경고: 파일 로드 오류. 건너뜁니다. ({file_path.name}, 오류: {e})")
                continue
            
            # 지정된 횟수만큼 증강 수행
            for _ in range(args.count_per_file):
                local_rng = np.random.default_rng(rng.integers(0, 2**32 - 1))
                y = augment_once(x, local_rng, noise_range, time_range, amp_range)
                save_augmented_series(y, label_out_dir, label, augmented_file_counter)
                augmented_file_counter += 1

    print(f"\n[완료] 데이터 증강이 완료되었습니다. 결과는 '{out_dir}' 폴더를 확인하세요.")

def build_argparser() -> argparse.ArgumentParser:
    """커맨드 라인 인자 파서를 생성합니다."""
    p = argparse.ArgumentParser(description="Basic 1D time-series augmentation for labeled directories.")
    p.add_argument("--data-dir", type=str, default="orig_data", help="<label>/*.npy 형태의 원본 데이터가 있는 루트 폴더")
    p.add_argument("--out-dir", type=str, default="augmented_data", help="증강된 데이터가 저장될 루트 폴더")
    p.add_argument("--count-per-file", type=int, default=10, help="각 원본 파일 당 생성할 증강 데이터 개수")
    p.add_argument("--seed", type=int, default=42, help="결과 재현을 위한 랜덤 시드")
    p.add_argument("--noise-std-min", type=float, default=0.01)
    p.add_argument("--noise-std-max", type=float, default=0.08)
    p.add_argument("--time-scale-min", type=float, default=0.92)
    p.add_argument("--time-scale-max", type=float, default=1.21)
    p.add_argument("--amp-scale-min", type=float, default=0.9)
    p.add_argument("--amp-scale-max", type=float, default=1.5)
    return p

if __name__ == "__main__":
    args = build_argparser().parse_args()
    run(args)