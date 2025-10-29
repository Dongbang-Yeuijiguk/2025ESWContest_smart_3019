from __future__ import annotations
import argparse
import time
from pathlib import Path # ⭐️ 디렉토리 스캔을 위해 추가

# trainer.py에서 메인 로직 함수를 가져옵니다.
from model.trainer import train_main

def print_dataset_summary(data_root: str):
    """⭐️ 데이터셋 루트 폴더를 스캔하여 각 레이블별 파일 개수를 출력하는 함수"""
    print("\n--- 데이터셋 요약 ---")
    root_path = Path(data_root)
    if not root_path.is_dir():
        print(f"❌ 오류: '{data_root}' 디렉토리를 찾을 수 없습니다.")
        return

    total_files = 0
    label_counts = {}
    
    # data_root 바로 아래에 있는 폴더들을 레이블로 간주
    label_dirs = sorted([d for d in root_path.iterdir() if d.is_dir()])
    
    if not label_dirs:
        print(f"⚠️  경고: '{data_root}' 디렉토리에서 레이블 폴더를 찾을 수 없습니다.")
        return

    for label_dir in label_dirs:
        label_name = label_dir.name
        # 각 레이블 폴더 안의 .npy 파일 개수를 셉니다.
        num_files = len(list(label_dir.glob("*.npy")))
        if num_files > 0:
            label_counts[label_name] = num_files
            total_files += num_files

    if not label_counts:
        print(f"⚠️  경고: '{data_root}' 내의 레이블 폴더에서 .npy 파일을 찾을 수 없습니다.")
        return
        
    print(f"총 {len(label_counts)}개의 레이블, {total_files}개의 .npy 파일을 찾았습니다.")
    for label, count in label_counts.items():
        print(f"  - {label:<20}: {count}개")
    print("---------------------\n")


def build_argparser():
    """
    단순화된 커맨드 라인 인자 파서를 생성합니다.
    대부분의 설정은 model/config.py에서 관리합니다.
    """
    ap = argparse.ArgumentParser(description="Train a CSI classifier on preprocessed .npy data.")
    
    # --- 실행 시 필수적으로 필요한 인자 ---
    ap.add_argument("data_root", type=str, 
                    help="전처리된 .npy 파일들이 있는 루트 폴더 (예: preprocessed/)")
    
    # --- 실행마다 달라질 수 있는 주요 옵션 ---
    ap.add_argument("--run-name", type=str, default=f"run_{time.strftime('%Y%m%d-%H%M%S')}", 
                    help="이번 학습 실행의 고유 이름 (결과 폴더명으로 사용)")
    ap.add_argument("--resume", type=str, default=None, 
                    help="학습을 재개할 체크포인트 파일 경로 (예: results/run_xxx/last.pt)")
    ap.add_argument("--eval-only", action="store_true", 
                    help="학습 없이 평가만 수행. --resume 플래그와 함께 사용해야 함")

    return ap

def main():
    """메인 실행 함수"""
    args = build_argparser().parse_args()
    
    # ⭐️ 학습 시작 전 데이터셋 요약 정보 출력
    print_dataset_summary(args.data_root)
    
    # 파싱된 인자를 train_main 함수로 전달하여 학습을 시작합니다.
    train_main(args)

if __name__ == "__main__":
    main()

'''
## 사용 예시 ##

# 1. 새로운 학습 시작하기
# preprocessed/ 폴더의 데이터를 사용하여 'resnet18_v1' 이름으로 학습 실행
python -m model.run preprocessed/ --run-name "resnet18_v1"

# 2. 이전 학습 이어서 재개하기
# 'resnet18_v1' 실행 결과 중 마지막 체크포인트를 불러와서 학습 재개
python -m model.run preprocessed/ --run-name "resnet18_v1" --resume "results/resnet18_v1/last.pt"

# 3. 학습된 모델로 평가만 수행하기
# 'resnet18_v1'의 가장 좋았던 모델을 불러와 평가만 진행
python -m model.run preprocessed/ --run-name "resnet18_v1_eval" --resume "results/resnet18_v1/best.pt" --eval-only

# 참고: Epoch, Batch Size, Learning Rate 등 모든 하이퍼파라미터는
# 이제 'model/config.py' 파일에서 수정합니다.
'''
