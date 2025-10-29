# train_data_parser.py
# CSI 데이터 학습용 데이터 파서

from __future__ import annotations
from pathlib import Path
from typing import Callable, Iterator, List, Tuple, Dict, Optional
import numpy as np
from tqdm.auto import tqdm # tqdm 임포트

# 타입 힌트: preprocess_fn은 파일 경로를 받아 전처리된 numpy 배열을 반환
PreprocessFn = Callable[[str], np.ndarray]

def scan_dataset(
    root: str | Path,
    exts: Tuple[str, ...] = (".csv", ".xlsx", ".xls")
) -> Tuple[List[Tuple[str, int, str]], List[str]]:
    """
    dataset/<label_name>/*.{csv,xlsx,xls} 구조를 스캔해 (path, label_idx, label_name) 리스트와
    label_names(인덱스→라벨) 배열을 반환.
    """
    root = Path(root)
    if not root.exists():
        raise FileNotFoundError(f"No such directory: {root}")

    label_names = sorted([p.name for p in root.iterdir() if p.is_dir()])
    label_to_idx: Dict[str, int] = {name: i for i, name in enumerate(label_names)}

    samples: List[Tuple[str, int, str]] = []
    for label in label_names:
        d = root / label
        for ext in exts:
            for fp in d.glob(f"*{ext}"):
                samples.append((str(fp), label_to_idx[label], label))

    if not samples:
        raise RuntimeError(f"No files found under {root} with exts={exts}")
    return samples, label_names


def iter_preprocessed(
    data_root: str | Path,
    preprocess_fn: PreprocessFn,
    exts: Tuple[str, ...] = (".csv", ".xlsx", ".xls"),
    on_error: str = "warn",  # "warn" | "raise" | "skip"
    desc: Optional[str] = "Processing files", # tqdm 설명 추가
) -> Iterator[Tuple[np.ndarray, int, str]]:
    """
    폴더/파일을 순회하며 전처리 함수를 적용해 (X, y, path) 를 yield.
    진행률 표시줄(progress bar)이 표시됩니다.
    """
    samples, _ = scan_dataset(data_root, exts)

    # [개선] samples 리스트를 tqdm으로 감싸 진행률 표시
    for path, y, _label in tqdm(samples, desc=desc):
        try:
            X = preprocess_fn(path)
        except Exception as e:
            msg = f"[preprocess error] {path}: {e}"
            if on_error == "raise":
                raise
            elif on_error == "warn":
                # tqdm 진행률 표시줄과 겹치지 않게 tqdm.write 사용
                tqdm.write(msg)
            # on_error == "skip": 아무 것도 안 함
            if on_error in ("warn", "skip"):
                continue
        yield X, y, path


def load_preprocessed_to_memory(
    data_root: str | Path,
    preprocess_fn: PreprocessFn,
    exts: Tuple[str, ...] = (".csv", ".xlsx", ".xls"),
    strict_stack: bool = False,  # True면 shape 안 맞을 때 에러, False면 list 유지
    desc: Optional[str] = "Loading to memory", # tqdm 설명 추가
) -> Tuple[List[np.ndarray] | np.ndarray, np.ndarray, List[str], List[str]]:
    """
    모든 샘플을 메모리로 불러와 (Xs, ys, paths, label_names) 반환.
    진행률 표시줄(progress bar)이 표시됩니다.
    """
    samples, label_names = scan_dataset(data_root, exts)

    X_list: List[np.ndarray] = []
    y_list: List[int] = []
    p_list: List[str] = []

    # [개선] samples 리스트를 tqdm으로 감싸 진행률 표시
    for path, y, _label in tqdm(samples, desc=desc):
        X = preprocess_fn(path)
        X_list.append(X)
        y_list.append(y)
        p_list.append(path)

    if strict_stack:
        Xs = np.stack(X_list, axis=0)
    else:
        Xs = X_list

    return Xs, np.asarray(y_list, dtype=np.int64), p_list, label_names


def save_preprocessed_to_disk(
    data_root: str | Path,
    out_dir: str | Path,
    preprocess_fn: PreprocessFn,
    exts: Tuple[str, ...] = (".csv", ".xlsx", ".xls"),
    keep_tree: bool = True,  # True면 라벨 디렉토리 구조를 그대로 유지
    overwrite: bool = False,
    desc: Optional[str] = "Saving to disk", # tqdm 설명 추가
) -> List[str]:
    """
    전처리 결과를 .npy로 디스크에 저장하고, 저장된 경로 리스트를 반환.
    진행률 표시줄(progress bar)이 표시됩니다.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    samples, _ = scan_dataset(data_root, exts)
    saved_paths: List[str] = []

    # [개선] samples 리스트를 tqdm으로 감싸 진행률 표시
    for path, _y, label in tqdm(samples, desc=desc):
        src = Path(path)
        rel_name = src.stem + ".npy"
        dst_dir = (out_dir / label) if keep_tree else out_dir
        dst = dst_dir / rel_name

        if dst.exists() and not overwrite:
            saved_paths.append(str(dst))
            continue

        X = preprocess_fn(path)
        dst_dir.mkdir(parents=True, exist_ok=True)
        np.save(str(dst), X)
        saved_paths.append(str(dst))

    return saved_paths