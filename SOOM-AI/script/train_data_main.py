# train_data_main.py
# CSI 학습용 데이터 처리 메인 스크립트

from utils.data_preprocessing import preprocess_csi_data
from utils.train_data_parser import iter_preprocessed, load_preprocessed_to_memory, save_preprocessed_to_disk

data_path = "../dataset"  # 원본 CSI 엑셀 파일들이 있는 폴더
preprocessed_path = "preprocessed"  # 전처리된 .npy 파일들이 저장될 폴더

# 1) 제너레이터로 바로 돌리기
print(">>> [1/3] Processing data with generator...")
# iter_preprocessed 함수 내부에서 tqdm이 돌면서 진행률을 표시합니다.
for X, y, path in iter_preprocessed(data_path, preprocess_csi_data, desc="Generator Processing"):
    # X: 전처리된 배열, y: 정수 라벨, path: 원본 경로
    pass
print("[Done]\n")


# 2) 전부 메모리로 적재
print(">>> [2/3] Loading all data into memory...")
# load_preprocessed_to_memory가 내부적으로 iter_preprocessed를 사용하므로
# 자동으로 진행률 표시줄이 나타납니다.
Xs, ys, paths, label_names = load_preprocessed_to_memory(
    data_path,
    preprocess_csi_data,
    strict_stack=False,  # True로 하면 np.stack 시도
    desc="Loading to Memory" # 설명을 바꿔줄 수 있습니다.
)
print(f"[Done] Loaded {len(Xs)} samples into memory.\n")


# 3) 전처리 결과를 .npy로 캐싱
print(f">>> [3/3] Caching preprocessed files to {preprocessed_path}/...")
saved = save_preprocessed_to_disk(
    data_root=data_path,
    out_dir=preprocessed_path,
    preprocess_fn=preprocess_csi_data,
    overwrite=False
)
# 진행률 표시는 save_preprocessed_to_disk 함수 내부에서 처리됩니다.
print(f"[Done] Saved {len(saved)} files under {preprocessed_path}/")