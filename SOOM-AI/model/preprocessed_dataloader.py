# model/preprocessed_dataloader.py
from __future__ import annotations
from pathlib import Path
from typing import List, Tuple, Optional

import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader
from sklearn.model_selection import train_test_split

class CsiDataset(Dataset):
    """
    전처리된 .npy 파일 경로 리스트를 받아 데이터를 로드하는 PyTorch Dataset.
    """
    def __init__(self, file_paths: List[Path], labels: List[int], add_channel_dim: bool):
        self.file_paths = file_paths
        self.labels = labels
        self.add_channel_dim = add_channel_dim

    def __len__(self) -> int:
        return len(self.file_paths)
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, int, str]:
        path = self.file_paths[idx]
        label = self.labels[idx]
        
        data = np.load(path)
        tensor = torch.from_numpy(data).float()
        
        # ✅ 1D CNN에 맞게 차원 변경
        # (길이,) -> (1, 길이)
        if tensor.ndim == 1:
            tensor = tensor.unsqueeze(0)
            
        return tensor, label, str(path)

def make_preprocessed_dataloaders(
    preprocessed_root: str,
    batch_size: int,
    num_workers: int,
    seed: int,
    add_channel_dim: bool,
    target_labels: Optional[List[str]] = None,
    val_size: float = 0.15,
    test_size: float = 0.15,
) -> Tuple[DataLoader, DataLoader, DataLoader, List[str]]:
    """
    전처리된 .npy 파일들로부터 train/validation/test 데이터로더를 생성합니다.
    """
    root = Path(preprocessed_root)
    
    if target_labels:
        # config에서 지정한 레이블만 사용
        label_names = sorted([label for label in target_labels if (root / label).is_dir()])
        print(f"지정된 레이블 사용: {label_names}")
    else:
        # 지정하지 않으면 모든 하위 폴더를 레이블로 간주 (숨김 폴더 제외)
        label_names = sorted([d.name for d in root.iterdir() if d.is_dir() and not d.name.startswith('.')])
        print(f"디렉토리에서 모든 레이블 자동 탐색: {label_names}")

    if not label_names:
        raise FileNotFoundError(f"'{root}' 디렉토리에서 레이블 폴더를 찾을 수 없습니다.")

    label_map = {name: i for i, name in enumerate(label_names)}

    all_files, all_labels = [], []
    for label_name in label_names:
        label_idx = label_map[label_name]
        files = list((root / label_name).glob("*.npy"))
        all_files.extend(files)
        all_labels.extend([label_idx] * len(files))

    if not all_files:
        raise FileNotFoundError(f"'{root}' 디렉토리에서 .npy 파일을 찾을 수 없습니다.")

    # Train / Validation / Test 데이터 분할
    X_train_val, X_test, y_train_val, y_test = train_test_split(
        all_files, all_labels,
        test_size=test_size,
        random_state=seed,
        stratify=all_labels
    )
    
    # 남은 train_val 데이터에서 train / validation 분할
    relative_val_size = val_size / (1.0 - test_size)
    X_train, X_val, y_train, y_val = train_test_split(
        X_train_val, y_train_val,
        test_size=relative_val_size,
        random_state=seed,
        stratify=y_train_val
    )

    # 각 데이터셋에 대한 CsiDataset 인스턴스 생성
    train_ds = CsiDataset(X_train, y_train, add_channel_dim)
    val_ds = CsiDataset(X_val, y_val, add_channel_dim)
    test_ds = CsiDataset(X_test, y_test, add_channel_dim)

    # 데이터로더 생성
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=num_workers, pin_memory=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=num_workers, pin_memory=True)
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False, num_workers=num_workers, pin_memory=True)
    
    print(f"데이터셋 분할 완료: Train={len(train_ds)}, Val={len(val_ds)}, Test={len(test_ds)}")

    return train_loader, val_loader, test_loader, label_names