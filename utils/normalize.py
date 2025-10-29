# utils/normalize.py
# CSI 진폭 정규화 함수

import numpy as np

def amplitude_normalization(csi_matrix: np.ndarray) -> np.ndarray:
    """
    CSI amplitude normalization.
    
    Args:
        csi_matrix (np.ndarray): shape = (T, Ns) 
            T = time steps, Ns = number of subcarriers
            Each entry can be complex (H(f_k, t)).
    
    Returns:
        np.ndarray: normalized power response, same shape as input
    """
    # 1. amplitude (power) 계산: |H|^2
    power = np.abs(csi_matrix) ** 2  # shape: (T, Ns)
    
    # 2. 전체 서브캐리어 power 합 (axis=1: 각 시점 t 마다)
    total_power = np.sum(power, axis=1, keepdims=True)  # shape: (T, 1)
    
    # 3. 정규화: 각 서브캐리어 power / 전체 power
    normalized = power / total_power  # shape: (T, Ns)
    
    return normalized
