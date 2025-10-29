import numpy as np
from typing import Tuple

def fft_lowpass_filter(
    data_1d: np.ndarray,
    cutoff_freq_ratio: float = 0.05,
) -> np.ndarray:
    """
    PCA로 축소된 1차원 시계열 데이터에 FFT 기반 저역 통과 필터를 적용합니다.

    Args:
        data_1d: PCA로 축소된 1차원 데이터 (T,) 형태.
        cutoff_freq_ratio: 필터링할 주파수의 비율. 
                           (0 < ratio < 0.5, N/2 지점에서 N * ratio 지점까지의 성분을 남김)
                           예: 0.05는 전체 주파수 범위의 5%만 남김.
        sampling_rate: 데이터의 실제 샘플링 속도 (Hz). 이 값이 제공되면 cutoff_freq_ratio 대신
                       실제 주파수(Hz)를 기준으로 필터링할 수 있지만, 여기서는 비율을 사용합니다.
    
    Returns:
        저역 통과 필터가 적용된 1차원 데이터 (T,) 형태.
    """
    # 데이터 형태 확인 및 (T,)로 변환
    if data_1d.ndim == 2 and data_1d.shape[1] == 1:
        data_1d = data_1d.flatten()
    elif data_1d.ndim != 1:
        raise ValueError("입력 데이터는 1차원(T,) 또는 2차원(T, 1) 형태여야 합니다.")
        
    T = data_1d.shape[0]

    # 1. FFT 수행
    # data_fft: 복소수 배열 (DC 성분부터 Nyquist 주파수까지 포함)
    data_fft = np.fft.fft(data_1d)
    
    # 2. 필터 마스크 생성 (저역 통과 필터)
    # FFT 결과의 인덱스는 0부터 T-1까지. 0은 DC, T/2 근처는 Nyquist 주파수.
    # 대칭성을 고려하여 T/2 지점에서 필터링해야 함.
    cutoff_index = int(T * cutoff_freq_ratio)
    
    # 마스크 생성: 저주파 성분(0 ~ cutoff_index)만 남기고 나머지는 0으로 설정
    mask = np.zeros(T, dtype=bool)
    
    # DC 및 양의 주파수 성분 (0에서 cutoff_index - 1)
    mask[:cutoff_index] = True
    
    # 음의 주파수 성분 (대칭되는 부분)
    # T - (cutoff_index - 1) 부터 T-1 까지
    mask[T - cutoff_index:] = True 
    
    # 3. 필터 적용
    data_fft_filtered = data_fft * mask
    
    # 4. iFFT (역 고속 푸리에 변환) 수행
    data_filtered = np.fft.ifft(data_fft_filtered)
    
    # 실수 성분만 추출 (필터링된 결과는 실수여야 함)
    return np.real(data_filtered)