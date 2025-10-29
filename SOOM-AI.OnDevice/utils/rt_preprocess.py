import pandas as pd
import numpy as np
from scipy.interpolate import interp1d

# 같은 utils 폴더에 있는 signal_processing 모듈에서 함수들을 가져옴
from . import signal_processing as sp

class RealtimePreprocessor:
    """
    CSI 데이터 전처리 파이프라인을 캡슐화하는 클래스.
    타임스탬프 기반 리샘플링을 포함한 모든 단계를 순서대로 실행하여
    모델 입력에 맞는 최종 1D 신호를 생성합니다.
    """
    def __init__(self, pca_components: int = 1, filter_ratio: float = 0.05):
        """
        Args:
            pca_components (int): PCA로 축소할 주성분 개수.
            filter_ratio (float): FFT 저역 통과 필터의 컷오프 비율.
        """
        self.pca_components = pca_components
        self.filter_ratio = filter_ratio

    def _resample_multichannel_signal(self, df: pd.DataFrame, target_size: int) -> np.ndarray:
        """
        타임스탬프를 기반으로 다채널 CSI 신호를 고정된 크기로 리샘플링합니다.

        Args:
            df (pd.DataFrame): 'timestamp'와 'amplitude' 컬럼을 가진 데이터프레임
            target_size (int): 리샘플링 후의 목표 샘플 개수 (예: 240)

        Returns:
            np.ndarray: (target_size, num_subcarriers) 형태의 리샘플링된 신호
        """
        # (N, num_subcarriers) 형태의 2D 배열로 변환
        amplitudes = np.vstack(df['amplitude'].to_numpy())
        
        # 원본 시간 축 (초 단위)
        original_timestamps = df['timestamp'].to_numpy()
        original_time_axis = original_timestamps - original_timestamps[0]

        # 새로운 균일한 시간 축 생성 (0초부터 마지막 시간까지 target_size개)
        new_time_axis = np.linspace(original_time_axis.min(), original_time_axis.max(), target_size)

        # 각 서브캐리어 채널별로 보간(interpolation) 수행
        num_subcarriers = amplitudes.shape[1]
        resampled_amplitudes = np.zeros((target_size, num_subcarriers))

        for i in range(num_subcarriers):
            # 1D 보간 함수 생성
            interp_func = interp1d(original_time_axis, amplitudes[:, i], kind='linear', fill_value="extrapolate")
            # 새로운 시간 축에 맞춰 값 계산
            resampled_amplitudes[:, i] = interp_func(new_time_axis)
            
        return resampled_amplitudes

    def run(self, csi_df: pd.DataFrame, model_input_size: int) -> np.ndarray:
        """
        전체 전처리 파이프라인을 실행합니다.

        Args:
            csi_df (pd.DataFrame): InfluxConnector로부터 받은 'timestamp'와 'amplitude' 컬럼을 가진 DF.
            model_input_size (int): 모델이 요구하는 최종 입력 크기 (예: 240)

        Returns:
            np.ndarray: 모든 전처리가 완료된 1차원 신호 데이터.
        """
        # 1. 리샘플링 (가변 길이 -> 고정 길이)
        # 타임스탬프를 이용해 가변적인 개수의 데이터를 모델 입력 크기(240)에 맞게 변환
        resampled_data = self._resample_multichannel_signal(csi_df, model_input_size)
        
        # 2. 노이즈 제거 (DWT)
        denoised_amp = sp.dwt_denoise_matrix(resampled_data)
        
        # 3. 정규화 (Standardization)
        standardized_amp = sp.standardize_matrix(denoised_amp)
        
        # 4. 차원 축소 (PCA)
        pca_result = sp.pca_52_subcarriers(standardized_amp, n_components=self.pca_components)
        
        # 5. 저역 통과 필터 (FFT Filter)
        final_signal = sp.fft_lowpass_filter(pca_result, cutoff_freq_ratio=self.filter_ratio)
        
        return final_signal

