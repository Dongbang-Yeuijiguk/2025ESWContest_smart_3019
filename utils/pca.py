import numpy as np
from sklearn.decomposition import PCA
from typing import Optional

def pca_52_subcarriers(
    data: np.ndarray,
    n_components: int = 10
) -> np.ndarray:
    """
    52개의 서브캐리어(특징)에 대해 PCA를 적용하여 차원을 축소합니다.

    Args:
        data: 입력 CSI 데이터. 
              (T, F=52) 형태 또는 (B, T, F=52) 형태여야 합니다.
        n_components: 축소할 주성분(서브캐리어)의 개수. (1 <= n_components <= 52)

    Returns:
        PCA가 적용된 데이터.
        입력 형태가 (T, F)이면 (T, n_components)로,
        (B, T, F)이면 (B, T, n_components)로 반환됩니다.
    """
    if data.shape[-1] != 52:
        raise ValueError(f"마지막 차원(서브캐리어 개수)은 52여야 합니다. 현재: {data.shape[-1]}")
    if not 1 <= n_components <= 52:
        raise ValueError(f"n_components는 1에서 52 사이여야 합니다. 현재: {n_components}")

    original_shape = data.shape
    
    # 1. 3D (B, T, F)를 2D (B*T, F)로 변환
    if data.ndim == 3:
        B, T, F = original_shape
        # (B, T, F) -> (B*T, F)
        data_2d = data.reshape(-1, F)
    elif data.ndim == 2:
        T, F = original_shape
        # (T, F)
        data_2d = data
        B = 1 # 배치 차원이 없음을 표시
    else:
        raise ValueError(f"입력 데이터는 2차원 (T, F) 또는 3차원 (B, T, F) 형태여야 합니다. Got shape {original_shape}")

    # 2. PCA 적용
    # PCA는 내부적으로 데이터를 평균 0, 표준편차 1로 스케일링하지 않으므로,
    # 필요하다면 이전에 표준화(Standardization)를 수행해야 합니다.
    # 여기서는 서브캐리어 간의 분산 차이가 중요하다고 가정하고 스케일링 없이 진행합니다.
    pca = PCA(n_components=n_components)
    
    # data_2d는 (샘플 수, 특징 수) 형태
    data_pca = pca.fit_transform(data_2d) # (B*T, n_components) 또는 (T, n_components)

    # 3. 결과 형태 복원
    if data.ndim == 3:
        # (B*T, n_components) -> (B, T, n_components)
        result_shape = (B, T, n_components)
        return data_pca.reshape(result_shape)
    else: # data.ndim == 2
        # (T, n_components)
        return data_pca