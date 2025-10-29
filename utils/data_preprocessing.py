# data_preprocessing.py
# CSI 데이터 전처리 파이프라인

from utils.extract import amp_phase_from_csi
from utils.load import load_csi_data
from utils.normalize import amplitude_normalization
from utils.noise_filtering import dwt_denoise_matrix
from utils.crop import crop_time
from utils.csi_amp_visualize import plot_csi_amp_heatmap
from utils.pca import pca_52_subcarriers
from utils.fft_filter import fft_lowpass_filter
# from utils.kalman_filter import kalman_denoise_matrix

import model.config as C


def preprocess_csi_data(excel_file):
    # CSI 데이터 로드
    data = load_csi_data(excel_file)
    
    # 진폭 및 위상 추출
    amp, _ = amp_phase_from_csi(data)

    # 시간축 크롭
    # cropped_amp = crop_time(amp, window_size=C.INPUT_LENGTH)
    
    # 진폭 정규화
    normalized_amp = amplitude_normalization(amp)

    # 노이즈 제거
    noise_filtered_amp = dwt_denoise_matrix(normalized_amp)
    # noise_filtered_amp = kalman_denoise_matrix(normalized_amp)

    # pca
    pca_amp = pca_52_subcarriers(noise_filtered_amp, 1)

    # fft lowpass filter
    fft_filtered = fft_lowpass_filter(pca_amp)

    return fft_filtered