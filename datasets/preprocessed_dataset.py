from __future__ import annotations
import random
from pathlib import Path
from typing import List, Tuple, Optional, Dict

import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader
from sklearn.model_selection import train_test_split

class PreprocessedCSIDataset(Dataset):
    """
    미리 전처리되어 저장된 .npy 파일을 로드하는 데이터셋.
    각 .npy 파일은 (Time, Features) 형태의 2D 배열이라고 가정합니다.
    """
    def __init__(
        self,
        file_paths: List[Path],
        labels: List[int],
        input_length: int,
        add_channel_dim: bool = True,
    ):
        super().__init__()
        self.file_paths = file_paths
        self.labels = labels
        self.input_length = input_length
        self.add_channel_dim = add_channel_dim
        
        # ⭐️ 세그먼테이션 인덱스 구축 (메모리 효율적)
        # NPY 파일이 이미 (input_length, F)로 저장되었다면 이 로직은 불필요합니다.
        # NPY 파일이 (T > input_length, F)로 저장되었다고 가정합니다.
        self.index = []
        for i, path in enumerate(file_paths):
            data = np.load(path, mmap_mode='r') # ❗️메모리 매핑으로 우선 로드
            num_frames = data.shape[0]
            label = self.labels[i]
            
            # ❗️ (T, F) 데이터를 (input_length, F)로 자르는 로직
            # ❗️ `InitialTrainer`의 config.py에서 C.STRIDE 값을 가져와야 합니다.
            stride = self.input_length // 2 # 예시: 50% overlap
            
            for start in range(0, num_frames - self.input_length + 1, stride):
                self.index.append((i, start, label))
        
        # ❗️ NPY 파일을 미리 로드하여 캐시 (선택)
        # self.cache = [np.load(p) for p in self.file_paths]

    def __len__(self) -> int:
        return len(self.index)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, int, Path]:
        file_idx, start_frame, label = self.index[idx]
        file_path = self.file_paths[file_idx]

        # ❗️ 캐시를 사용하지 않고 매번 로드
        data = np.load(file_path) # (T, F)
        
        # 세그먼트 추출
        segment = data[start_frame : start_frame + self.input_length] # (L, F)
        
        if self.add_channel_dim:
            # (L, F) -> (C=1, L, F)
            # ❗️Simple1DCNN은 (C, L) 또는 (L, C)가 아닌 (C=1, L)을 기대할 수 있습니다.
            # ❗️`classifier.py`의 입력 형태 (Batch, 1, Length)에 맞게 수정
            # ❗️PCA (L, 1) -> (1, L)
            segment = segment.transpose(1, 0) # (1, L)

        segment_tensor = torch.from_numpy(segment.astype(np.float32))
        return segment_tensor, label, file_path

def make_preprocessed_dataloaders(
    preprocessed_root: str | Path,
    label_map: Dict[str, int],
    batch_size: int,
    num_workers: int,
    seed: int,
    train_val_split: float = 0.9,
    add_channel_dim: bool = True,
    input_length: int = 500, # ❗️ 설정 파일에서 가져와야 함
) -> Tuple[DataLoader, DataLoader, List[str]]:
    
    root = Path(preprocessed_root)
    all_files, all_labels = [], []
    
    label_names = sorted(label_map.keys(), key=lambda k: label_map[k])
    
    for label_name in label_names:
        label_dir = root / label_name
        if label_dir.is_dir():
            files = sorted(list(label_dir.glob("*.npy")))
            all_files.extend(files)
            all_labels.extend([label_map[label_name]] * len(files))

    if not all_files:
        raise FileNotFoundError(f"No .npy files found in {root}")

    # Train / Validation 분리
    paths_train, paths_val, labels_train, labels_val = train_test_split(
        all_files, all_labels,
        train_size=train_val_split,
        random_state=seed,
        shuffle=True,
        stratify=all_labels
    )

    ds_train = PreprocessedCSIDataset(paths_train, labels_train, input_length, add_channel_dim)
    ds_val = PreprocessedCSIDataset(paths_val, labels_val, input_length, add_channel_dim)

    dl_train = DataLoader(ds_train, batch_size, shuffle=True, num_workers=num_workers, pin_memory=True, drop_last=True)
    dl_val = DataLoader(ds_val, batch_size, shuffle=False, num_workers=num_workers, pin_memory=True)
    
    return dl_train, dl_val, label_names
