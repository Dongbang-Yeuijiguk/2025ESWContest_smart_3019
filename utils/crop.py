# utils/crop.py
# CSI 데이터의 시간축 크롭 함수 (window_size 기반)

import numpy as np

def crop_time(x: np.ndarray, window_size: int) -> np.ndarray:
    """
    앞에서부터 window_size만큼만 남긴다.
    """
    return x[:window_size, :]