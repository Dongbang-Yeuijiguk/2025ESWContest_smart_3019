import numpy as np
import pandas as pd

# ❗️[필수]❗️
# 이 함수들이 동작하려면 `utils/` 폴더에
# extract, load, normalize, noise_filtering, crop, pca, fft_filter
# 모듈이 모두 존재해야 합니다.
from utils.extract import amp_phase_from_csi
# from utils.load import load_csi_data # 파일 로드 대신 DataFrame을 받도록 수정
from utils.normalize import amplitude_normalization
from utils.noise_filtering import dwt_denoise_matrix
from utils.crop import crop_time
from utils.pca import pca_52_subcarriers
from utils.fft_filter import fft_lowpass_filter
# from utils.kalman_filter import kalman_denoise_matrix

def preprocess_csi_dataframe(df: pd.DataFrame) -> np.ndarray:
    """
    InfluxDB에서 받은 DataFrame(raw CSI)을 전처리합니다.
    (기존 data_preprocessing.py 로직을 DataFrame 기반으로 수정)
    """
    # 1. DataFrame에서 CSI 데이터 추출
    # InfluxDB에서 'data' 컬럼에 복소수 배열이 문자열 등으로 저장된 경우
    # 이 부분에서 파싱이 필요할 수 있습니다.
    # 지금은 df.values가 (T, F) 형태의 복소수 데이터라고 가정합니다.
    # 만약 'data' 컬럼에만 데이터가 있다면:
    # csi_data = np.array(df['data'].tolist(), dtype=np.complex64)
    csi_data = df.values.astype(np.complex64) # ❗️실제 데이터 형태에 맞게 수정 필요

    # 2. 진폭 및 위상 추출
    amp, _ = amp_phase_from_csi(csi_data)

    # 3. 시간축 크롭 (필요시)
    # amp = crop_time(amp, window_size=C.INPUT_LENGTH)
    
    # 4. 진폭 정규화
    normalized_amp = amplitude_normalization(amp)

    # 5. 노이즈 제거
    noise_filtered_amp = dwt_denoise_matrix(normalized_amp)

    # 6. PCA
    pca_amp = pca_52_subcarriers(noise_filtered_amp, 1)

    # 7. FFT 저역 통과 필터
    fft_filtered = fft_lowpass_filter(pca_amp)

    return fft_filtered
