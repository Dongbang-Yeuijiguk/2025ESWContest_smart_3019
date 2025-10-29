import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import argparse
import sys
from pathlib import Path
from tqdm import tqdm

def analyze_threshold(data_root: str):
    """
    'empty'와 'presence'로 라벨링된 전처리된 .npy 데이터의 통계적 특성을 분석하여
    최적의 분류 임계값을 찾습니다.
    """
    root_path = Path(data_root)
    labels_to_process = ['empty', 'presence']
    
    print("=" * 50)
    print("통계 기반 임계값 분석 시작 (.npy 파일 기반)")
    print("=" * 50)

    # --- 1. 각 레이블별 데이터 처리 및 특징 추출 ---
    print("[1/2] 데이터 처리 및 분산(variance) 계산 중...")
    features = {'empty': [], 'presence': []}

    for label in labels_to_process:
        data_dir = root_path / label
        if not data_dir.is_dir():
            print(f"⚠️  경고: '{label}' 폴더를 찾을 수 없어 건너뜁니다.")
            continue
        
        # ⭐️ 데이터 파일을 .csv가 아닌 .npy로 탐색
        files = list(data_dir.glob("*.npy"))
        if not files:
            print(f"⚠️  경고: '{label}' 폴더에서 .npy 파일을 찾을 수 없습니다.")
            continue

        print(f"\n'{label}' 레이블 처리 중 ({len(files)}개 파일)...")
        for file_path in tqdm(files, desc=f"Processing {label}"):
            try:
                # ⭐️ 전처리된 1D 신호를 .npy 파일에서 직접 로드
                processed_signal = np.load(file_path)
                
                # 통계 특징 계산 (분산)
                variance = np.var(processed_signal)
                features[label].append(variance)
            except Exception as e:
                print(f"\n파일 처리 중 오류: {file_path.name} - {e}")

    # --- 2. 결과 분석 및 시각화 ---
    print("\n[2/2] 결과 분석 및 시각화 중...")
    
    empty_vars = np.array(features['empty'])
    presence_vars = np.array(features['presence'])

    if len(empty_vars) == 0 and len(presence_vars) == 0:
        print("❌ 처리할 데이터가 없습니다. 데이터 경로를 확인하세요.")
        return

    # 기술 통계 출력
    print("\n--- 분산(Variance) 통계 ---")
    if len(empty_vars) > 0:
        print(f"Empty    | Cnt: {len(empty_vars)}, Mean: {np.mean(empty_vars):.6f}, Std: {np.std(empty_vars):.6f}, Max: {np.max(empty_vars):.6f}")
    if len(presence_vars) > 0:
        print(f"Presence | Cnt: {len(presence_vars)}, Mean: {np.mean(presence_vars):.6f}, Std: {np.std(presence_vars):.6f}, Min: {np.min(presence_vars):.6f}")
    
    # 히스토그램 및 KDE 플롯 시각화
    plt.figure(figsize=(12, 6))
    sns.histplot(empty_vars, color="blue", label=f"Empty (N={len(empty_vars)})", kde=True, stat="density", common_norm=False)
    sns.histplot(presence_vars, color="red", label=f"Presence (N={len(presence_vars)})", kde=True, stat="density", common_norm=False)
    plt.title("Distribution of Signal Variance (Empty vs. Presence)", fontsize=16)
    plt.xlabel("Signal Variance")
    plt.ylabel("Density")
    plt.legend()
    plt.grid(True)
    
    print("\n플롯을 확인하여 두 분포를 가장 잘 나누는 임계값을 찾으세요.")
    print("두 분포의 교차점이나 'Empty' 분포의 최대값이 좋은 후보가 될 수 있습니다.")
    print("찾은 값을 config.py의 PRESENCE_VARIANCE_THRESHOLD에 반영하세요.")
    plt.show()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="전처리된 CSI 데이터(.npy)의 통계적 특성을 분석하여 'empty'와 'presence'를 구분하는 임계값을 찾습니다."
    )
    parser.add_argument(
        "data_root",
        type=str,
        help="분석할 데이터의 루트 폴더. 하위에 'empty', 'presence' 폴더가 있어야 합니다."
    )
    args = parser.parse_args()
    
    analyze_threshold(args.data_root)
